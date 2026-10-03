"""Kafka publisher and consumer adapters using Avro and Schema Registry."""

import logging
import os
from typing import Any, cast

from confluent_kafka import Consumer, KafkaError, KafkaException, SerializingProducer
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import (
    MessageField,
    SerializationContext,
    StringSerializer,
)

from racestream.application.telemetry import telemetry_to_payload
from racestream.domain.models import TelemetryEvent
from racestream.infrastructure.schema_registry import (
    create_schema_registry_client,
    load_telemetry_schema,
)

LOGGER = logging.getLogger(__name__)


class AvroKafkaPublisher:
    """Publish validated telemetry events to a Kafka topic."""

    def __init__(self, topic: str) -> None:
        """Create a Kafka producer backed by Schema Registry.

        :param topic: Destination topic for telemetry events.
        """
        schema_registry = create_schema_registry_client()
        serializer = AvroSerializer(
            schema_registry,
            load_telemetry_schema(),
            to_dict=lambda event, _context: telemetry_to_payload(event),
        )
        self._topic = topic
        self._producer = SerializingProducer(
            {
                "bootstrap.servers": os.environ.get(
                    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
                ),
                "key.serializer": StringSerializer("utf_8"),
                "value.serializer": serializer,
                "client.id": "racestream-simulator",
                "acks": "all",
            }
        )

    def publish(self, event: TelemetryEvent) -> None:
        """Enqueue one telemetry event using car ID as the Kafka key.

        :param event: Event to serialize and publish.
        """
        self._producer.produce(
            topic=self._topic,
            key=event.car_id,
            value=event,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def close(self) -> None:
        """Flush pending records before shutting down.

        :raises TimeoutError: If records remain after the flush timeout.
        """
        remaining = self._producer.flush(timeout=15.0)
        if remaining:
            raise TimeoutError(f"{remaining} telemetry record(s) were not delivered")

    @staticmethod
    def _on_delivery(error: KafkaError | None, message: Any) -> None:
        """Log asynchronous delivery results without logging payload contents."""
        if error is not None:
            LOGGER.error(
                "Kafka delivery failed",
                extra={
                    "topic": message.topic(),
                    "key": message.key(),
                    "error": str(error),
                },
            )
            return
        LOGGER.debug(
            "Kafka event delivered",
            extra={"topic": message.topic(), "partition": message.partition()},
        )


class AvroKafkaConsumer:
    """Consume, deserialize, and explicitly commit telemetry events."""

    def __init__(self, topic: str, group_id: str) -> None:
        """Create a Kafka consumer for the telemetry contract.

        :param topic: Topic to subscribe to.
        :param group_id: Consumer group identifier.
        """
        self._topic = topic
        registry = create_schema_registry_client()
        self._deserializer = AvroDeserializer(registry, load_telemetry_schema())
        self._consumer = Consumer(
            {
                "bootstrap.servers": os.environ.get(
                    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
                ),
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "client.id": f"racestream-consumer-{group_id}",
            }
        )
        self._consumer.subscribe([topic])

    def poll(self, timeout: float = 1.0) -> dict[str, object] | None:
        """Read and deserialize one event, committing only after success.

        :param timeout: Maximum time in seconds to wait for a message.
        :return: Decoded event payload, or ``None`` when no event is available.
        :raises KafkaException: If Kafka reports a non-retriable consume error.
        :raises ValueError: If a message cannot be deserialized.
        """
        message = self._consumer.poll(timeout)
        if message is None:
            return None
        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(error)

        payload = cast(
            dict[str, object] | None,
            self._deserializer(
                message.value(),
                SerializationContext(self._topic, MessageField.VALUE),
            ),
        )
        if payload is None:
            raise ValueError("Kafka message did not contain a telemetry event")
        self._consumer.commit(message=message, asynchronous=False)
        return payload

    def close(self) -> None:
        """Close the Kafka consumer and leave its consumer group."""
        self._consumer.close()