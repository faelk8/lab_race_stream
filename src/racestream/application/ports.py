"""Ports required by application use cases."""

from typing import Protocol

from racestream.domain.models import (
    CarConfiguration,
    RaceConfiguration,
    RaceResult,
    RaceSnapshot,
    TelemetryEvent,
)


class EventPublisher(Protocol):
    """Outbound port for publishing telemetry events."""

    def publish(self, event: TelemetryEvent) -> None:
        """Publish one event to an external event stream.

        :param event: Immutable telemetry event to publish.
        """

    def close(self) -> None:
        """Flush and release the publisher's external resources."""


class RaceRepository(Protocol):
    """Outbound port for car configuration and race persistence."""

    def seed_default_cars(self) -> None:
        """Insert default cars without overwriting existing configuration."""

    def list_car_configurations(self) -> tuple[CarConfiguration, ...]:
        """Return all configured cars in stable car-ID order."""

    def save_car_configuration(
        self,
        configuration: CarConfiguration,
    ) -> CarConfiguration:
        """Persist and return one validated car configuration.

        :param configuration: Configuration to insert or update.
        :return: Persisted configuration.
        """

    def start_race(self, configuration: RaceConfiguration) -> None:
        """Persist a race as running before telemetry publication.

        :param configuration: Race timing and circuit configuration.
        """

    def finish_race(self, race_id: str, results: tuple[RaceResult, ...]) -> None:
        """Persist final results and mark the race finished.

        :param race_id: Race identifier to complete.
        :param results: Final result snapshot for every car.
        """

    def get_latest_race(self) -> RaceSnapshot | None:
        """Return the most recently created race, if one exists."""