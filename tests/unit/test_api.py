"""Tests for REST car configuration with injected infrastructure ports."""

import asyncio

from fastapi.testclient import TestClient

from racestream.domain.models import (
    CarConfiguration,
    RaceConfiguration,
    RaceResult,
    RaceSnapshot,
)
from racestream.domain.simulator import create_default_car_configurations
from racestream.interfaces.api import create_app
from racestream.interfaces.kafka_hub import KafkaTelemetryHub


class FakeRaceRepository:
    """In-memory implementation of the race repository port."""

    def __init__(self) -> None:
        """Load deterministic profiles for API tests."""
        self.configurations = list(create_default_car_configurations())

    def seed_default_cars(self) -> None:
        """Keep the in-memory car profiles unchanged."""

    def list_car_configurations(self) -> tuple[CarConfiguration, ...]:
        """Return the test profiles in insertion order."""
        return tuple(self.configurations)

    def save_car_configuration(
        self,
        configuration: CarConfiguration,
    ) -> CarConfiguration:
        """Update one in-memory car configuration.

        :param configuration: Setup to persist.
        :return: The saved setup.
        """
        for index, current in enumerate(self.configurations):
            if current.car_id == configuration.car_id:
                self.configurations[index] = configuration
                return configuration
        raise KeyError(configuration.car_id)

    def start_race(self, configuration: RaceConfiguration) -> None:
        """Implement the repository port for API-only tests.

        :param configuration: Race configuration.
        """

    def finish_race(self, race_id: str, results: tuple[RaceResult, ...]) -> None:
        """Implement the repository port for API-only tests.

        :param race_id: Race identifier.
        :param results: Race results.
        """

    def get_latest_race(self) -> RaceSnapshot | None:
        """Return no race before a runner has started."""
        return None


class FakeTelemetryHub(KafkaTelemetryHub):
    """Kafka hub double that does not start a background thread."""

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Implement hub startup without connecting to Kafka.

        :param loop: Event loop owned by the test client.
        """

    def stop(self) -> None:
        """Implement hub shutdown without external resources."""


def test_car_configuration_can_be_updated_through_rest() -> None:
    """The API persists validated setup using its injected repository."""
    repository = FakeRaceRepository()
    app = create_app(repository, FakeTelemetryHub())

    with TestClient(app) as client:
        response = client.put(
            "/api/cars/CAR-01",
            json={
                "driver_id": "DRV-01",
                "car_weight_kg": 830.0,
                "driver_weight_kg": 76.0,
                "top_speed_kmh": 340.0,
                "tire_compound": "soft",
            },
        )

    assert response.status_code == 200
    assert response.json()["top_speed_kmh"] == 340.0
    assert response.json()["tire_compound"] == "soft"


def test_car_configuration_rejects_invalid_performance_values() -> None:
    """The API rejects vehicle limits outside the supported domain range."""
    app = create_app(FakeRaceRepository(), FakeTelemetryHub())

    with TestClient(app) as client:
        response = client.put(
            "/api/cars/CAR-01",
            json={
                "driver_id": "DRV-01",
                "car_weight_kg": 830.0,
                "driver_weight_kg": 76.0,
                "top_speed_kmh": 500.0,
                "tire_compound": "soft",
            },
        )

    assert response.status_code == 422


def test_legacy_setup_update_preserves_team_and_strategy() -> None:
    """Um cliente antigo pode editar a massa preservando os metadados novos."""
    repository = FakeRaceRepository()
    original = repository.configurations[2]
    app = create_app(repository, FakeTelemetryHub())
    with TestClient(app) as client:
        response = client.put(
            f"/api/cars/{original.car_id}",
            json={
                "driver_id": original.driver_id,
                "car_weight_kg": 500.0,
                "driver_weight_kg": original.driver_weight_kg,
                "top_speed_kmh": original.top_speed_kmh,
                "tire_compound": original.tire_compound.value,
            },
        )
    assert response.status_code == 200
    assert response.json()["team_id"] == original.team_id
    assert response.json()["strategy"] == "C"
    assert response.json()["driver_height_m"] == original.driver_height_m
    assert response.json()["driver_name"] == original.driver_name
    assert response.json()["driver_country_code"] == original.driver_country_code


def test_driver_name_and_country_can_be_edited() -> None:
    """A API salva nome e país do piloto junto aos metadados existentes."""
    from dataclasses import asdict

    repository = FakeRaceRepository()
    original = repository.configurations[0]
    payload = {
        **asdict(original),
        "driver_name": "Ana Souza",
        "driver_country_code": "BR",
    }
    app = create_app(repository, FakeTelemetryHub())
    with TestClient(app) as client:
        response = client.put(f"/api/cars/{original.car_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["driver_name"] == "Ana Souza"
    assert repository.configurations[0].driver_country_code == "BR"


def test_driver_country_rejects_malformed_code() -> None:
    """O código do país precisa conter duas letras maiúsculas."""
    from dataclasses import asdict

    repository = FakeRaceRepository()
    original = repository.configurations[0]
    payload = {**asdict(original), "driver_country_code": "brasil"}
    app = create_app(repository, FakeTelemetryHub())
    with TestClient(app) as client:
        response = client.put(f"/api/cars/{original.car_id}", json=payload)
    assert response.status_code == 422


def test_websocket_queue_preserves_a_complete_grid_burst() -> None:
    """A fila comporta a rajada de eventos dos vinte carros sem descartar o quadro."""
    hub = FakeTelemetryHub()
    queue = hub.subscribe()
    events: list[dict[str, object]] = [{"car_id": f"CAR-{i:02d}"} for i in range(1, 21)]
    for event in events:
        hub._broadcast(event)
    assert [queue.get_nowait() for _ in range(20)] == events
    hub.unsubscribe(queue)
