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
from pyspark.sql.functions import (
    sum as sum_values,
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
        sum_values("lap_time_ms").alias("sum_lap_time_ms"),
        countDistinct("event_id").alias("valid_lap_count"),
    )


def agregar_janela_voltas(voltas: DataFrame) -> DataFrame:
    """Resuma uma janela, contando voltas inválidas para validar cobertura."""
    unicas = voltas.dropDuplicates(["event_id"])
    return unicas.groupBy("race_id", "car_id").agg(
        countDistinct("event_id").alias("completed_lap_count"),
        sum_values(when(col("valid"), 1).otherwise(0)).alias("valid_lap_count"),
        min(when(col("valid"), col("lap_time_ms"))).alias("best_lap_time_ms"),
        max(when(col("valid"), col("lap_time_ms"))).alias("worst_lap_time_ms"),
        sum_values(when(col("valid"), col("lap_time_ms")).otherwise(0)).alias(
            "sum_lap_time_ms"
        ),
    )


def consolidar_agregados_volta(janelas: DataFrame) -> DataFrame:
    """Una resumos de micro-lotes em um agregado final por corrida e carro."""
    return janelas.groupBy("race_id", "car_id").agg(
        sum_values("completed_lap_count").alias("completed_lap_count"),
        sum_values("valid_lap_count").alias("valid_lap_count"),
        min("best_lap_time_ms").alias("best_lap_time_ms"),
        max("worst_lap_time_ms").alias("worst_lap_time_ms"),
        sum_values("sum_lap_time_ms").alias("sum_lap_time_ms"),
    ).withColumn(
        "average_lap_time_ms",
        when(
            col("valid_lap_count") > 0,
            col("sum_lap_time_ms") / col("valid_lap_count"),
        ).otherwise(lit(None).cast("double")),
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
    agregado_voltas_pronto: DataFrame | None = None,
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
    agregado_voltas = (
        agregado_voltas_pronto
        if agregado_voltas_pronto is not None
        else agregar_voltas_validas(voltas)
    )
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
            "sum_lap_time_ms",
            "completed_lap_count",
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


def processar_lote_voltas(lote: DataFrame, id_lote: int) -> None:
    """Grave voltas brutas e métricas por micro-lote nas camadas Bronze/Prata.

    Os caminhos incluem o ID estável do micro-lote. Se Spark repetir um lote
    após falha, `overwrite` substitui exatamente o mesmo conjunto de arquivos.
    """
    if not lote.limit(1).count():
        return
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    base = f"s3a://{bucket}"
    arquivadas = lote.select(
        col("timestamp").alias("kafka_timestamp"),
        col("topic"),
        col("partition").alias("kafka_partition"),
        col("offset").alias("kafka_offset"),
        col("key").alias("event_key"),
        col("value").alias("avro_envelope"),
        col("headers").alias("kafka_headers"),
    )
    decodificadas = decodificar(arquivadas, "lap_completed")
    eventos = decodificadas.select(
        "topic",
        "kafka_timestamp",
        "kafka_partition",
        "kafka_offset",
        "avro_envelope",
        "evento.*",
    ).dropDuplicates(["event_id"])
    for linha in eventos.select("race_id").distinct().collect():
        race_id = linha["race_id"]
        corrida = eventos.filter(col("race_id") == race_id)
        prefixo = f"{base}/corridas/{race_id}"
        lote_nome = f"lote-{id_lote:020d}"
        corrida.select(
            "topic", "kafka_timestamp", "kafka_partition", "kafka_offset",
            "event_id", "event_time", "race_id", "car_id", "lap",
            "avro_envelope",
        ).write.mode("overwrite").parquet(
            f"{prefixo}/bronze/janelas_volta/{lote_nome}"
        )
        corrida.select(
            "event_id", "race_id", "car_id", "lap", "lap_time_ms", "valid",
            "sectors_ms", "pit_lap", "race_position", "event_time",
            "kafka_partition", "kafka_offset",
        ).write.mode("overwrite").parquet(
            f"{prefixo}/prata/voltas_incrementais/{lote_nome}"
        )
        agregar_janela_voltas(corrida).write.mode("overwrite").parquet(
            f"{prefixo}/prata/agregados_volta/{lote_nome}"
        )
        logger.info(
            "Micro-lote %s materializado para a corrida %s", id_lote, race_id
        )


def _listar_lotes_validos(spark: SparkSession, caminho: str) -> list[str]:
    """Retorne somente diretórios de micro-lote com marcador Spark de sucesso."""
    raiz = spark._jvm.org.apache.hadoop.fs.Path(caminho)
    fs = raiz.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration())
    if not fs.exists(raiz):
        return []
    lotes = []
    for status in fs.listStatus(raiz):
        lote = status.getPath()
        sucesso = spark._jvm.org.apache.hadoop.fs.Path(f"{lote}/_SUCCESS")
        if status.isDirectory() and lote.getName().startswith("lote-") and fs.exists(
            sucesso
        ):
            lotes.append(lote.toString())
    return lotes


def _ler_voltas_incrementais(
    spark: SparkSession, prefixo: str, final: DataFrame
) -> tuple[DataFrame, DataFrame] | None:
    """Use os fatos incrementais somente quando cobrem o quadro final inteiro."""
    fatos_path = _listar_lotes_validos(
        spark, f"{prefixo}/prata/voltas_incrementais"
    )
    agregados_path = _listar_lotes_validos(
        spark, f"{prefixo}/prata/agregados_volta"
    )
    if not fatos_path or not agregados_path:
        return None
    fatos = spark.read.parquet(*fatos_path).dropDuplicates(["event_id"])
    agregados = consolidar_agregados_volta(spark.read.parquet(*agregados_path))
    esperado = final.select("race_id", "car_id", col("laps_completed").cast("long"))
    contagem_fatos = fatos.groupBy("race_id", "car_id").agg(
        countDistinct("event_id").alias("fact_lap_count")
    )
    cobertura = (
        esperado.join(
            agregados.select("race_id", "car_id", "completed_lap_count"),
            ["race_id", "car_id"],
            "left",
        )
        .join(contagem_fatos, ["race_id", "car_id"], "left")
        .filter(
            (coalesce(col("completed_lap_count"), lit(0)) != col("laps_completed"))
            | (coalesce(col("fact_lap_count"), lit(0)) != col("laps_completed"))
            | (col("completed_lap_count") != col("fact_lap_count"))
        )
    )
    if cobertura.limit(1).count():
        logger.info("Agregados incrementais incompletos; usando fallback batch")
        return None
    return fatos, agregados


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

    prefixo = f"{base}/corridas/{race_id}"
    incremental = _ler_voltas_incrementais(spark, prefixo, final)
    if incremental is not None:
        voltas, agregado_voltas_pronto = incremental
    else:
        voltas_decodificadas = _decodificar_corrida(
            arquivo, "lap_completed", race_id
        )
        agregado_voltas_pronto = None
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

    bronze_registros = []
    for topico in TOPICOS:
        if topico == "lap_completed" and incremental is not None:
            lotes_bronze = _listar_lotes_validos(
                spark, f"{prefixo}/bronze/janelas_volta"
            )
            if lotes_bronze:
                registros_volta = (
                    spark.read.parquet(*lotes_bronze)
                    .dropDuplicates(["event_id"])
                    .select(
                        "topic",
                        "kafka_timestamp",
                        "kafka_partition",
                        "kafka_offset",
                        "event_id",
                        "event_time",
                        "race_id",
                        "avro_envelope",
                    )
                )
                if registros_volta.limit(1).count():
                    bronze_registros.append(registros_volta)
            continue
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

    classificacao = gerar_classificacao(
        final, voltas, paradas, agregado_voltas_pronto
    )
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
