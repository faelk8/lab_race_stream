"""Arquive envelopes Kafka da corrida em Parquet no MinIO."""

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date


def criar_sessao() -> SparkSession:
    """Crie uma sessão Spark com acesso ao armazenamento S3 local."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.environ.get("MINIO_ROOT_USER", "racestream")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "racestream-local-only")
    session = (
        SparkSession.builder.appName("RaceStreamArquivoKafka")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .getOrCreate()
    )
    session.sparkContext.setLogLevel(os.environ.get("SPARK_LOG_LEVEL", "WARN"))
    return session


def main() -> None:
    """Leia tópicos race.* e mantenha arquivo Parquet com checkpoint S3A."""
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    topics = os.environ.get(
        "SPARK_KAFKA_TOPICS",
        "race.telemetry.raw.v4,race.telemetry.validated.v4,race.timing.crossed.v1,"
        "race.lap.completed.v1,race.pitstop.v1,race.incident.v1,race.control.v1,"
        "race.state.v1,race.analytics.v1,race.dead-letter.v1",
    )
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    base_path = f"s3a://{bucket}/telemetry_raw"
    checkpoint_path = f"s3a://{bucket}/_checkpoints/spark_kafka_archive_v1"
    spark = criar_sessao()
    kafka = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topics)
        .option("startingOffsets", os.environ.get("SPARK_STARTING_OFFSETS", "earliest"))
        .option("failOnDataLoss", "true")
        .option(
            "maxOffsetsPerTrigger",
            os.environ.get("SPARK_MAX_OFFSETS_PER_TRIGGER", "1000"),
        )
        .option("includeHeaders", "true")
        .load()
    )
    arquivo = kafka.select(
        col("timestamp").alias("kafka_timestamp"),
        col("topic"),
        col("partition").alias("kafka_partition"),
        col("offset").alias("kafka_offset"),
        col("key").alias("event_key"),
        col("value").alias("avro_envelope"),
        col("headers").alias("kafka_headers"),
    ).withColumn("event_date_utc", to_date(col("kafka_timestamp")))
    consulta = (
        arquivo.writeStream.format("parquet")
        .outputMode("append")
        .option("path", base_path)
        .option("checkpointLocation", checkpoint_path)
        .partitionBy("topic", "event_date_utc")
        .trigger(processingTime=os.environ.get("SPARK_TRIGGER_INTERVAL", "30 seconds"))
        .start()
    )
    consulta.awaitTermination()


if __name__ == "__main__":
    main()
