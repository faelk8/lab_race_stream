"""Verifique integridade básica do arquivo Parquet no MinIO."""

import json
import os

from arquivo_telemetria import criar_sessao
from pyspark.sql.functions import col, countDistinct


def validar() -> dict[str, int]:
    """Confira presença e integridade dos registros arquivados.

    :return: Quantidade arquivada e número de tópicos encontrados.
    :raises AssertionError: Se o arquivo não contém as colunas ou linhas esperadas.
    """
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    dados = criar_sessao().read.parquet(f"s3a://{bucket}/telemetry_raw")
    obrigatorias = {
        "kafka_timestamp",
        "topic",
        "kafka_partition",
        "kafka_offset",
        "event_key",
        "avro_envelope",
        "kafka_headers",
        "event_date_utc",
    }
    faltantes = obrigatorias.difference(dados.columns)
    assert not faltantes, f"Colunas ausentes: {sorted(faltantes)}"
    invalidos = dados.filter(
        col("kafka_timestamp").isNull()
        | col("topic").isNull()
        | col("kafka_partition").isNull()
        | col("kafka_offset").isNull()
        | col("avro_envelope").isNull()
    )
    assert invalidos.limit(1).count() == 0, "Há registros sem metadados obrigatórios"
    resumo = dados.agg(countDistinct("topic").alias("topicos")).first()
    chaves_repetidas = (
        dados.groupBy("topic", "kafka_partition", "kafka_offset")
        .count()
        .filter(col("count") > 1)
    )
    duplicados = chaves_repetidas.count()
    assert duplicados == 0, f"Há {duplicados} offsets Kafka duplicados no arquivo"
    quantidade = dados.count()
    assert quantidade > 0, "O arquivo Parquet ainda não contém eventos"
    return {"registros": quantidade, "topicos": int(resumo["topicos"])}


def main() -> None:
    """Imprima um resumo sem carregar valores de telemetria no terminal."""
    resultado = validar()
    print(json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    main()
