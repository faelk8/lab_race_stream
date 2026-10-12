"""Materialize as camadas medalhão locais para corridas finalizadas."""

import json
import logging
import os
import time
from typing import Any

from agregar_voltas import decodificar
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    avg,
    coalesce,
    col,
    countDistinct,
    explode,
    greatest,
    lit,
    max,
    min,
    row_number,
    udf,
    when,
)
from pyspark.sql.types import StringType
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)
TOPICOS = (
    "telemetry",
    "validated",
    "timing",
    "lap_completed",
    "pitstop",
    "incident",
    "control",
    "state",
    "analytics",
    "dead_letter",
)


def _bandeira_pais(codigo: str | None) -> str:
    """Converta um código ISO alfa-2 em bandeira Unicode quando for válido."""
    if codigo is None or len(codigo) != 2 or not codigo.isalpha():
        return ""
    return "".join(chr(127397 + ord(letra.upper())) for letra in codigo)


_emoji_bandeira = udf(_bandeira_pais, StringType())


def agregar_voltas_validas(voltas: DataFrame) -> DataFrame:
    """Resuma voltas válidas sem contar novamente eventos repetidos."""
    unicas = voltas.filter(col("valid")).dropDuplicates(["event_id"])
    return unicas.groupBy("race_id", "car_id").agg(
        min("lap_time_ms").alias("best_lap_time_ms"),
        max("lap_time_ms").alias("worst_lap_time_ms"),
        avg("lap_time_ms").alias("average_lap_time_ms"),
        countDistinct("event_id").alias("valid_lap_count"),
    )


def agregar_pit_stops(paradas: DataFrame) -> DataFrame:
    """Conte uma parada somente no evento de saída da faixa de boxes."""
    concluidas = paradas.filter(col("phase") == "exit").dropDuplicates(
        ["race_id", "car_id", "stop_number"]
    )
    return concluidas.groupBy("race_id", "car_id").agg(
        countDistinct("stop_number").alias("pit_stop_count")
    )


def gerar_classificacao(
    telemetria_final: DataFrame,
    voltas: DataFrame,
    paradas: DataFrame,
) -> DataFrame:
    """Una o estado final com métricas, ordene e identifique o pódio."""
    base = telemetria_final.select(
        "race_id",
        "car_id",
        "driver_id",
        "driver_name",
        "driver_country_code",
        "team_id",
        col("race_position").cast("int").alias("position"),
        col("best_lap_time_ms").cast("long").alias("state_best_lap_time_ms"),
        col("worst_lap_time_ms").cast("long").alias("state_worst_lap_time_ms"),
        col("pit_stops").cast("int").alias("state_pit_stop_count"),
    )
    agregado_voltas = agregar_voltas_validas(voltas)
    agregado_paradas = agregar_pit_stops(paradas)
    resultado = (
        base.join(agregado_voltas, ["race_id", "car_id"], "left")
        .join(agregado_paradas, ["race_id", "car_id"], "left")
        .withColumn(
            "pit_stop_count",
            greatest(col("pit_stop_count"), col("state_pit_stop_count")).cast(
                "int"
            ),
        )
        .withColumn("pit_stop_count", coalesce(col("pit_stop_count"), lit(0)))
        .withColumn(
            "best_lap_time_ms",
            coalesce(col("best_lap_time_ms"), col("state_best_lap_time_ms")),
        )
        .withColumn(
            "worst_lap_time_ms",
            coalesce(col("worst_lap_time_ms"), col("state_worst_lap_time_ms")),
        )
        .drop(
            "state_pit_stop_count",
            "state_best_lap_time_ms",
            "state_worst_lap_time_ms",
        )
        .withColumn(
            "podium_medal",
            when(col("position") == 1, lit("ouro"))
            .when(col("position") == 2, lit("prata"))
            .when(col("position") == 3, lit("bronze")),
        )
        .withColumn("country_flag", _emoji_bandeira(col("driver_country_code")))
        .withColumn("trophy", when(col("position") <= 3, lit("🏆")))
    )
    return resultado.orderBy("position", "car_id")


def _decodificar_corrida(
    arquivo: DataFrame, topico: str, race_id: str
) -> DataFrame | None:
    """Decodifique somente um tópico que contenha registros arquivados."""
    dados = arquivo.filter(col("topic") == topico)
    if not dados.limit(1).count():
        return None
    decodificado = decodificar(dados, topico)
    return decodificado.filter(col("evento.race_id") == race_id)


def _salvar_json(spark: SparkSession, caminho: str, payload: dict[str, Any]) -> None:
    """Grave um JSON único pelo filesystem Hadoop S3A do Spark."""
    configuracao = spark.sparkContext._jsc.hadoopConfiguration()
    destino = spark._jvm.org.apache.hadoop.fs.Path(caminho)
    sistema = destino.getFileSystem(configuracao)
    temporario = spark._jvm.org.apache.hadoop.fs.Path(f"{caminho}.tmp")
    fluxo = sistema.create(temporario, True)
    try:
        fluxo.write(bytearray(json.dumps(payload, ensure_ascii=False).encode("utf-8")))
    finally:
        fluxo.close()
    if sistema.exists(destino):
        sistema.delete(destino, False)
    if not sistema.rename(temporario, destino):
        raise OSError("Não foi possível finalizar o resumo ouro no MinIO")


def materializar_corrida(spark: SparkSession, race_id: str) -> bool:
    """Crie bronze, prata e ouro para uma corrida finalizada, se os dados bastam."""
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    base = f"s3a://{bucket}"
    arquivo = spark.read.parquet(f"{base}/telemetry_raw")
    estado_decodificado = _decodificar_corrida(arquivo, "state", race_id)
    voltas_decodificadas = _decodificar_corrida(arquivo, "lap_completed", race_id)
    paradas_decodificadas = _decodificar_corrida(arquivo, "pitstop", race_id)
    if estado_decodificado is None or not estado_decodificado.limit(1).count():
        return False

    estado = estado_decodificado.select("evento.*").filter(col("complete"))
    quadros = estado.select(
        col("snapshot_id").alias("frame_snapshot_id"),
        explode("cars").alias("carro"),
    ).select(col("frame_snapshot_id"), col("carro.telemetry.*"))
    janela = Window.partitionBy("race_id", "car_id").orderBy(
        col("frame_snapshot_id").desc()
    )
    final = (
        quadros.withColumn("ordem", row_number().over(janela))
        .filter(col("ordem") == 1)
        .drop("ordem")
    )
    quantidade_finalizados = final.filter(col("race_status") == "finished").count()
    quantidade_carros = final.select("car_id").distinct().count()
    if quantidade_carros == 0 or quantidade_finalizados < quantidade_carros:
        return False

    if voltas_decodificadas is None:
        voltas = final.limit(0).select(
            "race_id", "car_id", lit("").alias("event_id"),
            lit(0).cast("long").alias("lap_time_ms"),
            lit(False).alias("valid"),
        )
    else:
        voltas = voltas_decodificadas.select("evento.*")
    if paradas_decodificadas is None:
        paradas = final.limit(0).select(
            "race_id", "car_id", lit("").alias("event_id"),
            lit(0).alias("stop_number"), lit("").alias("phase"),
        )
    else:
        paradas = paradas_decodificadas.select("evento.*")

    prefixo = f"{base}/corridas/{race_id}"
    bronze_registros = []
    for topico in TOPICOS:
        decodificado = _decodificar_corrida(arquivo, topico, race_id)
        if decodificado is None:
            continue
        registros = decodificado.filter(col("evento.race_id") == race_id).select(
            col("topic"), col("kafka_timestamp"), col("kafka_partition"),
            col("kafka_offset"), col("evento.event_id").alias("event_id"),
            col("evento.event_time").alias("event_time"),
            col("evento.race_id").alias("race_id"), col("avro_envelope"),
        )
        if registros.limit(1).count():
            bronze_registros.append(registros)
    if not bronze_registros:
        return False
    bronze = bronze_registros[0]
    for registros in bronze_registros[1:]:
        bronze = bronze.unionByName(registros)
    bronze.write.mode("overwrite").parquet(f"{prefixo}/bronze/eventos")
    voltas.write.mode("overwrite").parquet(f"{prefixo}/prata/voltas")
    paradas.write.mode("overwrite").parquet(f"{prefixo}/prata/pit_stops")
    final.write.mode("overwrite").parquet(f"{prefixo}/prata/telemetria_final")

    classificacao = gerar_classificacao(final, voltas, paradas)
    classificacao.write.mode("overwrite").parquet(f"{prefixo}/ouro/classificacao")
    linhas = [linha.asDict(recursive=True) for linha in classificacao.collect()]
    _salvar_json(
        spark,
        f"{prefixo}/ouro/resumo.json",
        {"race_id": race_id, "classification": linhas},
    )
    logger.info("Camadas medalhão materializadas para %s", race_id)
    return True


def acompanhar_corridas(
    spark: SparkSession,
    intervalo_segundos: int = 30,
    parada: Any | None = None,
) -> None:
    """Materialize resultados ouro assim que o arquivamento registrar o término."""
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    raiz = f"s3a://{bucket}"
    fs = spark._jvm.org.apache.hadoop.fs.Path(raiz).getFileSystem(
        spark.sparkContext._jsc.hadoopConfiguration()
    )
    while parada is None or not parada.is_set():
        try:
            arquivo = spark.read.parquet(f"{raiz}/telemetry_raw")
            controles = arquivo.filter(col("topic") == "control")
            if controles.limit(1).count():
                eventos = decodificar(controles, "control").select("evento.*")
                ids = [
                    linha["race_id"]
                    for linha in eventos.filter(col("status") == "finished")
                    .select("race_id")
                    .distinct()
                    .collect()
                ]
                for race_id in ids:
                    resumo = spark._jvm.org.apache.hadoop.fs.Path(
                        f"{raiz}/corridas/{race_id}/ouro/resumo.json"
                    )
                    if not fs.exists(resumo):
                        try:
                            materializar_corrida(spark, race_id)
                        except Exception:
                            logger.exception(
                                "Falha ao materializar camadas da corrida %s", race_id
                            )
        except Exception:
            logger.exception("Falha ao verificar corridas finalizadas no MinIO")
        if parada is not None:
            parada.wait(intervalo_segundos)
        else:
            time.sleep(intervalo_segundos)
