"""Calcule desempenho por carro e confira paridade com o consumer online."""

import json
import os
from urllib.request import urlopen

from analitica_voltas import (
    agregar_voltas,
    analytics_mais_recente,
    comparar_agregados,
    resumir_paridade,
)
from arquivo_telemetria import criar_sessao
from pyspark.sql import DataFrame
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import (
    coalesce,
    col,
    conv,
    explode,
    expr,
    hex,
    substring,
    when,
)


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
    voltas_decodificadas = decodificar(arquivo, "lap_completed")
    voltas = voltas_decodificadas.select("evento.*")
    agregado = agregar_voltas(voltas)
    analytics = (
        decodificar(arquivo, "analytics")
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
    online = analytics_mais_recente(carros_online)
    comparacao = comparar_agregados(agregado, online)
    agregado.write.mode("overwrite").parquet(f"{base}/lap_performance")
    comparacao.write.mode("overwrite").parquet(f"{base}/consumer_parity")
    return resumir_paridade(comparacao)


def main() -> None:
    """Imprima somente contagens da execução analítica."""
    print(json.dumps(executar(), ensure_ascii=False))


if __name__ == "__main__":
    main()
