"""Application use case coordinating simulation and event publication."""

from racestream.application.ports import EventPublisher
from racestream.domain.simulator import RaceSimulator


class SimulationService:
    """Coordinate one simulation tick and publish its resulting events."""

    def __init__(self, simulator: RaceSimulator, publisher: EventPublisher) -> None:
        """Build the use case from injected domain and publishing dependencies.

        :param simulator: Domain simulator that advances car state.
        :param publisher: Outbound adapter implementing the event publisher port.
        """
        self._simulator = simulator
        self._publisher = publisher

    def publish_tick(self) -> int:
        """Advance the race and publish one event for each car.

        :return: Number of telemetry events published.
        """
        events = self._simulator.tick()
        for event in events:
            self._publisher.publish(event)
        return len(events)