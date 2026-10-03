"""Run the seeded race simulator and publish Avro telemetry to Kafka."""

import logging
import os
import time

from racestream.application.simulation_service import SimulationService
from racestream.domain.simulator import RaceSimulator
from racestream.infrastructure.kafka import AvroKafkaPublisher
from racestream.interfaces.logging_config import configure_logging


def main() -> None:
    """Run the simulator until interrupted by the operator."""
    configure_logging()
    logger = logging.getLogger(__name__)
    simulator = RaceSimulator(
        seed=int(os.environ.get("RACE_SEED", "42")),
        race_id=os.environ.get("RACE_ID", "race-local-001"),
        car_count=int(os.environ.get("RACE_CAR_COUNT", "20")),
    )
    topic = os.environ.get("KAFKA_TOPIC", "race.telemetry.raw")
    interval = float(os.environ.get("SIMULATION_INTERVAL_SECONDS", "1.0"))
    publisher = AvroKafkaPublisher(topic)
    service = SimulationService(simulator=simulator, publisher=publisher)

    logger.info(
        "Simulator started",
        extra={"race_id": simulator.race_id, "car_count": len(simulator.cars)},
    )
    try:
        while True:
            service.publish_tick()
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Simulator stopping")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()