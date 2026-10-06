"""Calcule desempenho por carro e confira paridade com o consumer online."""

import json
import os
from urllib.request import urlopen

from arquivo_telemetria import criar_sessao
from pyspark.sql import DataFrame
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import (
    avg,
    coalesce,
    col,
    conv,
    count,
    explode,
    expr,
    hex,
    max,
    min,
    row_number,
    substring,
    when,
)
from pyspark.sql.functions import (
    sum as soma,
)
from pyspark.sql.window import Window


def obter_schema(url: str) -> str:
    """Leia do Schema Registry a versão mais recente de um contrato.

    :param url: Endereço completo do recurso no Schema Registry.
    :return: Schema Avro serializado como JSON.
    """
    with urlopen(url, timeout=10) as resposta:
        return json.loads(resposta.read())["schema"]


def decodificar(dados: DataFrame, topico: str) -> DataFrame:
    """Decodifique envelopes Confluent pelo schema writer de cada ID.

    :param dados: Eventos brutos arquivados em Parquet.
    :param topico: Tópico Kafka cujos envelopes devem ser decodificados.
    :return: Eventos normalizados para o schema reader mais recente.
    """
    registro = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    subject = f"{topico}-value"
    reader = obter_schema(f"{registro}/subjects/{subject}/versions/latest")
    fonte = dados.filter(col("topic") == topico).withColumn(
        "schema_id",
        conv(hex(substring(col("avro_envelope"), 2, 4)), 16, 10).cast("int"),
    )
    ids = [
        linha["schema_id"] for linha in fonte.select("schema_id").distinct().collect()
    ]
    if not ids:
        raise ValueError(f"O arquivo não contém eventos do tópico {topico}")
    alternativas = []
    for schema_id in ids:
        writer = obter_schema(f"{registro}/schemas/ids/{schema_id}")
        decodificado = from_avro(
            expr("substring(avro_envelope, 6, length(avro_envelope) - 5)"),
            writer,
            {"avroSchema": reader},
        )
        alternativas.append(when(col("schema_id") == schema_id, decodificado))
    return fonte.select(coalesce(*alternativas).alias("evento"))


def executar() -> dict[str, int]:
    """Gere tabelas Parquet de voltas e compare com o resultado online.

    :return: Contagens de pares analisados, coincidentes e divergentes.
    """
    spark = criar_sessao()
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    base = f"s3a://{bucket}"
    arquivo = spark.read.parquet(f"{base}/telemetry_raw")
    voltas_decodificadas = decodificar(arquivo, "race.lap.completed.v1")
    voltas = (
        voltas_decodificadas.select("evento.*")
        .filter(col("valid"))
        .dropDuplicates(["event_id"])
    )
    agregado = voltas.groupBy("race_id", "car_id").agg(
        count("lap_time_ms").alias("voltas_validas"),
        min("lap_time_ms").alias("melhor_volta_ms"),
        max("lap_time_ms").alias("pior_volta_ms"),
        avg("lap_time_ms").alias("media_volta_ms"),
    )
    analytics = (
        decodificar(arquivo, "race.analytics.v1")
        .select("evento.*")
        .dropDuplicates(["event_id"])
    )
    carros_online = analytics.select(
        "race_id", "revision", explode("cars").alias("carro")
    ).select(
        "race_id",
        "revision",
        col("carro.car_id").alias("car_id"),
        col("carro.lap_count").alias("voltas_consumer"),
        col("carro.best_lap_time_ms").alias("melhor_consumer_ms"),
        col("carro.worst_lap_time_ms").alias("pior_consumer_ms"),
    )
    mais_recente = Window.partitionBy("race_id", "car_id").orderBy(
        col("revision").desc()
    )
    online = (
        carros_online.withColumn("ordem", row_number().over(mais_recente))
        .filter(col("ordem") == 1)
        .drop("ordem")
    )
    comparacao = agregado.join(online, ["race_id", "car_id"], "full")
    comparacao = comparacao.withColumn(
        "paridade",
        col("voltas_validas").eqNullSafe(col("voltas_consumer"))
        & col("melhor_volta_ms").eqNullSafe(col("melhor_consumer_ms"))
        & col("pior_volta_ms").eqNullSafe(col("pior_consumer_ms")),
    )
    agregado.write.mode("overwrite").parquet(f"{base}/lap_performance")
    comparacao.write.mode("overwrite").parquet(f"{base}/consumer_parity")
    totais = comparacao.agg(
        count("car_id").alias("carros"),
        count("paridade").alias("comparados"),
        count(expr("CASE WHEN paridade THEN 1 END")).alias("coincidentes"),
        soma(when(~col("paridade"), 1).otherwise(0)).alias("divergentes"),
    ).first()
    return {
        "carros": int(totais["carros"]),
        "comparados": int(totais["comparados"]),
        "coincidentes": int(totais["coincidentes"]),
        "divergentes": int(totais["divergentes"]),
    }


def main() -> None:
    """Imprima somente contagens da execução analítica."""
    print(json.dumps(executar(), ensure_ascii=False))


if __name__ == "__main__":
    main()
