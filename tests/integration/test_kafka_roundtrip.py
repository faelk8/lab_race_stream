"""Opt-in integration test for Kafka and Schema Registry round-trip."""

import os
import time
import uuid

import pytest
from confluent_kafka.admin import AdminClient, NewTopic  # type: ignore[attr-defined]

from racestream.domain.simulator import RaceSimulator
from racestream.infrastructure.kafka import AvroKafkaConsumer, AvroKafkaPublisher

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KAFKA_INTEGRATION") != "1",
    reason="set RUN_KAFKA_INTEGRATION=1 when Kafka and Schema Registry are running",
)


def test_event_is_published_and_deserialized_from_kafka() -> None:
    """A consumer receives the same event ID that the producer published."""
    topic = f"racestream-test-{uuid.uuid4().hex}"
    admin = AdminClient(
        {
            "bootstrap.servers": os.environ.get(
                "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
            )
        }
    )
    admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])[
        topic
    ].result(timeout=15)
    consumer = AvroKafkaConsumer(topic, f"integration-{uuid.uuid4()}")
    publisher = AvroKafkaPublisher(topic)
    expected_event = RaceSimulator(
        seed=19, car_count=1, race_id=f"test-{uuid.uuid4()}"
    ).tick()[0]

    try:
        publisher.publish(expected_event)
        publisher.close()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            payload = consumer.poll(timeout=1.0)
            if payload is not None and payload["event_id"] == expected_event.event_id:
                assert payload["car_id"] == expected_event.car_id
                assert payload["race_id"] == expected_event.race_id
                assert payload["schema_version"] == 3
                assert payload["tire_pressure_psi"] == expected_event.tire_pressure_psi
                assert payload["pit_stops"] == expected_event.pit_stops
                assert payload["overtaking_lane"] == expected_event.overtaking_lane
                return
        raise AssertionError("published event was not consumed before timeout")
    finally:
        consumer.close()
        admin.delete_topics([topic])[topic].result(timeout=15)
