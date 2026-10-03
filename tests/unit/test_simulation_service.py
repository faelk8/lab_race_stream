"""Tests for the application simulation use case and its publisher port."""

from racestream.application.simulation_service import SimulationService
from racestream.domain.models import TelemetryEvent
from racestream.domain.simulator import RaceSimulator


class InMemoryPublisher:
    """Test publisher that captures events without infrastructure."""

    def __init__(self) -> None:
        """Initialize an empty event collection."""
        self.events: list[TelemetryEvent] = []

    def publish(self, event: TelemetryEvent) -> None:
        """Capture one event for assertions.

        :param event: Event emitted by the application use case.
        """
        self.events.append(event)

    def close(self) -> None:
        """Implement the publisher port's resource lifecycle method."""


def test_simulation_service_publishes_each_car_event_through_port() -> None:
    """The use case depends on the publisher port, not Kafka itself."""
    publisher = InMemoryPublisher()
    service = SimulationService(
        simulator=RaceSimulator(seed=5, car_count=3),
        publisher=publisher,
    )

    published_count = service.publish_tick()

    assert published_count == 3
    assert [event.car_id for event in publisher.events] == [
        "CAR-01",
        "CAR-02",
        "CAR-03",
    ]