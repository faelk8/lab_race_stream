"""Testes de integração local das transformações Spark e da paridade online."""

from analitica_voltas import (
    agregar_voltas,
    analytics_mais_recente,
    comparar_agregados,
    resumir_paridade,
)
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)


def main() -> None:
    """Execute fixtures sem Kafka, PostgreSQL, MinIO ou corrida ativa."""
    spark = (
        SparkSession.builder.master("local[1]")
        .appName("RaceStreamTestesAnaliticos")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        voltas_schema = StructType(
            [
                StructField("event_id", StringType(), False),
                StructField("race_id", StringType(), False),
                StructField("car_id", StringType(), False),
                StructField("lap_time_ms", IntegerType(), False),
                StructField("valid", BooleanType(), False),
            ]
        )
        voltas = spark.createDataFrame(
            [
                ("lap-1", "race-fixture", "CAR-01", 90_000, True),
                ("lap-1", "race-fixture", "CAR-01", 90_000, True),
                ("lap-2", "race-fixture", "CAR-01", 100_000, True),
                ("lap-invalid", "race-fixture", "CAR-01", 70_000, False),
                ("lap-3", "race-fixture", "CAR-02", 95_000, True),
            ],
            voltas_schema,
        )
        agregado = agregar_voltas(voltas)
        resultados = {row["car_id"]: row.asDict() for row in agregado.collect()}
        assert resultados["CAR-01"]["voltas_validas"] == 2
        assert resultados["CAR-01"]["melhor_volta_ms"] == 90_000
        assert resultados["CAR-01"]["pior_volta_ms"] == 100_000
        assert resultados["CAR-02"]["voltas_validas"] == 1

        online_schema = StructType(
            [
                StructField("race_id", StringType(), False),
                StructField("revision", IntegerType(), False),
                StructField("car_id", StringType(), False),
                StructField("voltas_consumer", IntegerType(), False),
                StructField("melhor_consumer_ms", IntegerType(), False),
                StructField("pior_consumer_ms", IntegerType(), False),
            ]
        )
        online = spark.createDataFrame(
            [
                ("race-fixture", 1, "CAR-01", 9, 50_000, 150_000),
                ("race-fixture", 2, "CAR-01", 2, 90_000, 100_000),
                ("race-fixture", 1, "CAR-02", 1, 95_000, 95_000),
                ("race-fixture", 1, "CAR-03", 0, 0, 0),
            ],
            online_schema,
        )
        online_atual = analytics_mais_recente(online)
        comparacao = comparar_agregados(agregado, online_atual)
        resumo = resumir_paridade(comparacao)
        assert resumo == {
            "carros": 3,
            "comparados": 3,
            "coincidentes": 2,
            "divergentes": 1,
        }, resumo
        divergente = comparacao.filter("car_id = 'CAR-03'").first()
        assert divergente is not None and divergente["paridade"] is False
        print("Testes Spark aprovados: agregados, revisão mais recente e paridade.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
