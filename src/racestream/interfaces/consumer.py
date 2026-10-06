"""Run a logging consumer for decoded telemetry events."""

import logging
import os

from racestream.infrastructure.kafka import AvroKafkaConsumer
from racestream.interfaces.logging_config import configure_logging


def main() -> None:
    """Consume telemetry until interrupted by the operator."""
    configure_logging()
    logger = logging.getLogger(__name__)
    topic = os.environ.get("KAFKA_TOPIC", "telemetry")
    group_id = os.environ.get("KAFKA_CONSUMER_GROUP", "racestream-local-consumer")
    consumer = AvroKafkaConsumer(topic=topic, group_id=group_id)
    logger.info("Telemetry consumer started", extra={"topic": topic})
    try:
        while True:
            event = consumer.poll()
            if event is not None:
                logger.info(
                    "Telemetry received",
                    extra={
                        "race_id": event["race_id"],
                        "car_id": event["car_id"],
                        "lap": event["lap"],
                        "race_position": event["race_position"],
                    },
                )
    except KeyboardInterrupt:
        logger.info("Telemetry consumer stopping")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
