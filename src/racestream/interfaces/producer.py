"""Run the seeded race simulator and publish Avro telemetry to Kafka."""

import logging
import os
import time
from uuid import uuid4

from racestream.application.race_service import RaceRunService
from racestream.domain.models import RaceConfiguration
from racestream.domain.simulator import (
    RACE_DURATION_SECONDS,
    TARGET_LAPS,
    TRACK_LENGTH_M,
    RaceSimulator,
)
from racestream.infrastructure.kafka import AvroKafkaPublisher
from racestream.infrastructure.postgres_repository import PostgresRaceRepository
from racestream.interfaces.logging_config import configure_logging


def main() -> None:
    """Run the simulator until interrupted by the operator."""
    configure_logging()
    logger = logging.getLogger(__name__)
    repository = PostgresRaceRepository(
        os.environ.get(
            "DATABASE_URL",
            "postgresql://racestream:racestream@localhost:5432/racestream",
        )
    )
    repository.seed_default_cars()
    car_configurations = repository.list_car_configurations()
    topic = os.environ.get("KAFKA_TOPIC", "race.telemetry.raw")
    interval = float(os.environ.get("SIMULATION_INTERVAL_SECONDS", "0.1"))
    duration_seconds = float(
        os.environ.get("RACE_DURATION_SECONDS", str(RACE_DURATION_SECONDS))
    )
    target_laps = int(os.environ.get("RACE_TARGET_LAPS", str(TARGET_LAPS)))
    seed = int(os.environ.get("RACE_SEED", "42"))
    publisher = AvroKafkaPublisher(topic)

    logger.info("Race runner started", extra={"car_count": len(car_configurations)})
    try:
        while True:
            race_id = f"race-{uuid4().hex[:12]}"
            race_configuration = RaceConfiguration(
                race_id=race_id,
                duration_seconds=duration_seconds,
                target_laps=target_laps,
                track_length_m=TRACK_LENGTH_M,
            )
            repository.start_race(race_configuration)
            simulator = RaceSimulator(
                seed=seed,
                race_id=race_id,
                track_length_m=TRACK_LENGTH_M,
                race_duration_seconds=duration_seconds,
                target_laps=target_laps,
                car_configurations=car_configurations,
            )
            service = RaceRunService(simulator, publisher, repository)
            logger.info(
                "Race started",
                extra={"race_id": race_id, "target_laps": target_laps},
            )

            previous_tick = time.monotonic()
            while simulator.race_status == "running":
                tick_started = time.monotonic()
                elapsed = max(0.001, tick_started - previous_tick)
                service.publish_tick(elapsed)
                previous_tick = tick_started
                time.sleep(max(0.0, interval - (time.monotonic() - tick_started)))

            results = service.persist_results()
            logger.info(
                "Race finished",
                extra={
                    "race_id": race_id,
                    "winner_car_id": results[0].car_id,
                    "winner_best_lap_time_ms": results[0].best_lap_time_ms,
                },
            )
    except KeyboardInterrupt:
        logger.info("Race runner stopping")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()