"""Transformações Spark para agregados de voltas e paridade online."""

from pyspark.sql import DataFrame
from pyspark.sql.functions import avg, col, count, max, min, row_number
from pyspark.sql.window import Window


def agregar_voltas(voltas: DataFrame) -> DataFrame:
    """Agregue voltas válidas uma vez por evento/corrida/carro.

    :param voltas: Eventos decodificados do tópico `lap_completed`.
    :return: Contagem, melhor, pior e média por corrida/carro.
    """
    unicas = voltas.filter(col("valid")).dropDuplicates(["event_id"])
    return unicas.groupBy("race_id", "car_id").agg(
        count("lap_time_ms").alias("voltas_validas"),
        min("lap_time_ms").alias("melhor_volta_ms"),
        max("lap_time_ms").alias("pior_volta_ms"),
        avg("lap_time_ms").alias("media_volta_ms"),
    )


def analytics_mais_recente(carros_online: DataFrame) -> DataFrame:
    """Selecione a revisão mais recente do resumo online por carro.

    :param carros_online: Analytics achatados por corrida/revisão/carro.
    :return: Um registro online mais recente por corrida e carro.
    """
    mais_recente = Window.partitionBy("race_id", "car_id").orderBy(
        col("revision").desc()
    )
    return (
        carros_online.withColumn("ordem", row_number().over(mais_recente))
        .filter(col("ordem") == 1)
        .drop("ordem")
    )


def comparar_agregados(agregado: DataFrame, online: DataFrame) -> DataFrame:
    """Compare as métricas Spark e consumer por corrida e carro.

    :param agregado: Resultado de :func:`agregar_voltas`.
    :param online: Resultado de :func:`analytics_mais_recente`.
    :return: Junção completa, incluindo carros ausentes em um dos lados.
    """
    comparacao = agregado.join(online, ["race_id", "car_id"], "full")
    return comparacao.withColumn(
        "paridade",
        col("voltas_validas").eqNullSafe(col("voltas_consumer"))
        & col("melhor_volta_ms").eqNullSafe(col("melhor_consumer_ms"))
        & col("pior_volta_ms").eqNullSafe(col("pior_consumer_ms")),
    )


def resumir_paridade(comparacao: DataFrame) -> dict[str, int]:
    """Conte pares coincidentes e divergentes para o relatório da execução.

    :param comparacao: Saída de :func:`comparar_agregados`.
    :return: Contagens sem expor dados individuais no log.
    """
    from pyspark.sql.functions import expr, when
    from pyspark.sql.functions import sum as soma

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
