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


class RaceControl(Protocol):
    """Porta de coordenação persistente dos comandos de corrida."""

    def request_start(self, configuration: RaceConfiguration) -> RaceSnapshot:
        """Solicite uma corrida ou retorne a corrida ativa existente.

        :param configuration: Configuração da nova corrida.
        :return: Estado persistido da corrida solicitada ou já ativa.
        """

    def request_stop(self, race_id: str) -> RaceSnapshot:
        """Solicite a parada de uma corrida, preservando estados já encerrados.

        :param race_id: Identificador da corrida.
        :return: Estado persistido após a solicitação.
        """

    def claim_next_race(self) -> RaceConfiguration | None:
        """Reserve atomicamente a próxima corrida pendente.

        :return: Configuração reservada ou nenhum trabalho pendente.
        """

    def get_race_status(self, race_id: str) -> str:
        """Consulte o estado de controle de uma corrida.

        :param race_id: Identificador da corrida.
        :return: Estado atual.
        """

    def fail_race(self, race_id: str) -> None:
        """Registre uma falha durante a execução da corrida.

        :param race_id: Identificador da corrida.
        """
