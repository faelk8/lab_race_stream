"""Ports required by application use cases."""

from typing import Protocol

from racestream.domain.models import TelemetryEvent


class EventPublisher(Protocol):
    """Outbound port for publishing telemetry events."""

    def publish(self, event: TelemetryEvent) -> None:
        """Publish one event to an external event stream.

        :param event: Immutable telemetry event to publish.
        """

    def close(self) -> None:
        """Flush and release the publisher's external resources."""