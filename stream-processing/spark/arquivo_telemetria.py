"""Arquive envelopes Kafka da corrida em Parquet no MinIO."""

import os
from urllib.request import urlopen

from operational_health import OperationalHealth, serve_health
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date
from saude_stream import QueryHealth


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
    """Leia tópicos da corrida e mantenha arquivo Parquet com checkpoint S3A."""
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    topics = os.environ.get(
        "SPARK_KAFKA_TOPICS",
        "telemetry,validated,timing,lap_completed,pitstop,incident,control,"
        "state,analytics,dead_letter",
    )
    bucket = os.environ.get("MINIO_BUCKET", "racestream")
    base_path = f"s3a://{bucket}/telemetry_raw"
    checkpoint_path = f"s3a://{bucket}/_checkpoints/spark_kafka_archive_v2"
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
    health = OperationalHealth()
    server = serve_health(health, int(os.environ.get("HEALTH_PORT", "9102")))
    monitor = QueryHealth(float(os.environ.get("SPARK_STALL_TIMEOUT_SECONDS", "300")))
    try:
        while not consulta.awaitTermination(5):
            observed = monitor.observe(consulta)
            minio_ready = False
            try:
                endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
                with urlopen(f"{endpoint}/minio/health/ready", timeout=3) as response:
                    minio_ready = response.status == 200
            except OSError:
                pass  # A falha fica visível na readiness e na métrica de prontidão.
            health.heartbeat(
                inicializado=True,
                query=bool(observed.pop("query_ready")),
                minio=minio_ready,
            )
            for name, value in observed.items():
                health.set(name, value)
    finally:
        health.stop()
        server.shutdown()
        server.server_close()
        consulta.stop()
        spark.stop()


if __name__ == "__main__":
    main()
