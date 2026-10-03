"""Schema Registry configuration and versioned Avro schema loading."""

import os
from pathlib import Path

from confluent_kafka.schema_registry import SchemaRegistryClient

DEFAULT_SCHEMA_PATH = Path("schemas/telemetry-v1.avsc")


def schema_registry_url() -> str:
    """Return the configured Schema Registry URL.

    :return: HTTP URL for Schema Registry.
    """
    return os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081")


def create_schema_registry_client() -> SchemaRegistryClient:
    """Create a Schema Registry client from process configuration.

    :return: Configured Schema Registry client.
    """
    return SchemaRegistryClient({"url": schema_registry_url()})


def load_telemetry_schema() -> str:
    """Load the versioned telemetry Avro schema from disk.

    :return: Avro schema JSON text.
    :raises FileNotFoundError: If the configured schema file is missing.
    """
    schema_path = Path(os.environ.get("TELEMETRY_SCHEMA_PATH", DEFAULT_SCHEMA_PATH))
    return schema_path.read_text(encoding="utf-8")