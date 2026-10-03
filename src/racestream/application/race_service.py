"""Application use case for executing and completing a race."""

from racestream.application.ports import EventPublisher, RaceRepository
from racestream.domain.models import RaceResult
from racestream.domain.simulator import RaceSimulator


class RaceRunService:
    """Coordinate domain ticks, event publication, and final persistence."""

    def __init__(
        self,
        simulator: RaceSimulator,
        publisher: EventPublisher,
        repository: RaceRepository,
    ) -> None:
        """Create a race use case with injected outbound ports.

        :param simulator: Domain race simulator.
        :param publisher: Telemetry publication port.
        :param repository: Operational race persistence port.
        """
        self._simulator = simulator
        self._publisher = publisher
        self._repository = repository

    def publish_tick(self, elapsed_seconds: float) -> int:
        """Advance the race and publish all car snapshots.

        :param elapsed_seconds: Wall-clock duration since the previous tick.
        :return: Number of events published.
        """
        events = self._simulator.tick(elapsed_seconds)
        for event in events:
            self._publisher.publish(event)
        return len(events)

    def persist_results(self) -> tuple[RaceResult, ...]:
        """Persist final car positions and the configuration used by each car.

        :return: Final classification in race-position order.
        """
        results = tuple(
            RaceResult(
                race_id=self._simulator.race_id,
                car_id=car.car_id,
                race_position=car.race_position,
                laps_completed=car.lap - 1,
                last_lap_time_ms=car.last_lap_time_ms,
                best_lap_time_ms=car.best_lap_time_ms,
                car_weight_kg=car.configuration.car_weight_kg,
                driver_weight_kg=car.configuration.driver_weight_kg,
                top_speed_kmh=car.configuration.top_speed_kmh,
                tire_compound=car.tire_compound,
            )
            for car in sorted(self._simulator.cars, key=lambda item: item.race_position)
        )
        self._repository.finish_race(self._simulator.race_id, results)
        return results