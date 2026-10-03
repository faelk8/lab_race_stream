"""Tests for race execution through injected persistence and publisher ports."""

from racestream.application.race_service import RaceRunService
from racestream.domain.models import (
    CarConfiguration,
    RaceResult,
    TelemetryEvent,
    TireCompound,
)
from racestream.domain.simulator import RaceSimulator


class InMemoryPublisher:
    """Publisher test double that records published telemetry events."""

    def __init__(self) -> None:
        """Initialize an empty collection of telemetry events."""
        self.events: list[TelemetryEvent] = []

    def publish(self, event: TelemetryEvent) -> None:
        """Capture one telemetry event.

        :param event: Event emitted by the race service.
        """
        self.events.append(event)

    def close(self) -> None:
        """Implement the event publisher lifecycle contract."""


class InMemoryRaceRepository:
    """Repository test double that records race result persistence."""

    def __init__(self) -> None:
        """Initialize an empty final-result collection."""
        self.race_id: str | None = None
        self.results: tuple[RaceResult, ...] = ()

    def finish_race(self, race_id: str, results: tuple[RaceResult, ...]) -> None:
        """Capture the completed race results.

        :param race_id: Race identifier.
        :param results: Final race classification.
        """
        self.race_id = race_id
        self.results = results


def test_race_service_publishes_and_persists_result_snapshot() -> None:
    """The use case publishes events and persists results through ports."""
    configurations = tuple(
        CarConfiguration(
            car_id=f"CAR-{index:02d}",
            driver_id=f"DRV-{index:02d}",
            car_weight_kg=820.0,
            driver_weight_kg=75.0,
            top_speed_kmh=330.0,
            tire_compound=TireCompound.MEDIUM,
        )
        for index in range(1, 3)
    )
    simulator = RaceSimulator(seed=2, car_configurations=configurations)
    publisher = InMemoryPublisher()
    repository = InMemoryRaceRepository()
    service = RaceRunService(simulator, publisher, repository)  # type: ignore[arg-type]

    assert service.publish_tick(120.0) == 2
    results = service.persist_results()

    assert len(publisher.events) == 2
    assert repository.race_id == simulator.race_id
    assert repository.results == results
    assert [result.laps_completed for result in results] == [60, 60]