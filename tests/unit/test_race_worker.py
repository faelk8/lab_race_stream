"""Verificação das transições de controle sem serviços externos."""

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from test_api import FakeRaceRepository, FakeTelemetryHub
from test_race_service import InMemoryPublisher

from racestream.application.race_worker import RaceWorker
from racestream.domain.models import RaceConfiguration, RaceResult, RaceSnapshot
from racestream.interfaces.api import (
    CarConfigurationRequest,
    IncidentRequest,
    RaceStartRequest,
    create_app,
)


class ControlledRepository(FakeRaceRepository):
    """Armazene comandos e resultados em memória para os testes."""

    def __init__(self) -> None:
        """Inicialize um grid reduzido e nenhum comando."""
        super().__init__()
        self.configurations = self.configurations[:2]
        self.configuration: RaceConfiguration | None = None
        self.status = "stopped"
        self.results: tuple[RaceResult, ...] = ()

    def request_start(self, configuration: RaceConfiguration) -> RaceSnapshot:
        """Solicite início ou devolva a corrida já ativa."""
        if self.status not in ("queued", "running", "stopping"):
            self.configuration = configuration
            self.status = "queued"
        return self.get_latest_race()

    def get_latest_race(self) -> RaceSnapshot:
        """Retorne os metadados da corrida de teste."""
        config = self.configuration
        assert config is not None
        return RaceSnapshot(
            config.race_id,
            config.circuit_name,
            config.duration_seconds,
            config.target_laps,
            self.status,
            "2026-10-03",
            None,
        )

    def request_stop(self, race_id: str) -> RaceSnapshot:
        """Cancele uma solicitação ou interrompa a execução."""
        if self.configuration is None or race_id != self.configuration.race_id:
            raise KeyError(race_id)
        if self.status == "queued":
            self.status = "stopped"
        elif self.status == "running":
            self.status = "stopping"
        return self.get_latest_race()

    def request_pause(self, race_id: str) -> RaceSnapshot:
        if self.status == "running":
            self.status = "paused"
        return self.get_latest_race()

    def request_resume(self, race_id: str) -> RaceSnapshot:
        if self.status == "paused":
            self.status = "running"
        return self.get_latest_race()

    def claim_next_race(self) -> RaceConfiguration | None:
        """Reserve uma solicitação uma única vez."""
        if self.status != "queued":
            return None
        self.status = "running"
        return self.configuration

    def get_race_status(self, race_id: str) -> str:
        """Retorne o estado do comando atual."""
        return self.status

    def fail_race(self, race_id: str) -> None:
        """Registre uma falha explicitamente."""
        self.status = "failed"

    def finish_race(self, race_id: str, results: tuple[RaceResult, ...]) -> None:
        """Salve a classificação parcial ou final."""
        self.results = results
        self.status = "stopped" if self.status == "stopping" else "finished"


def test_stop_preserves_progress_and_worker_waits_for_another_start() -> None:
    """Parar não avança o relógio e não inicia outra corrida automaticamente."""
    repository = ControlledRepository()
    publisher = InMemoryPublisher()
    worker = RaceWorker(repository, repository, publisher)
    worker.step(10)
    assert not publisher.events
    repository.request_start(RaceConfiguration(race_id="teste"))
    worker.step(10)
    assert publisher.events[-1].elapsed_race_seconds == 0
    worker.step(0.1)
    previous = publisher.events[-2:]
    repository.request_stop("teste")
    worker.step(10)
    stopped = publisher.events[-2:]
    assert all(
        event.race_status == "stopped" and event.speed_kmh == 0 for event in stopped
    )
    assert [(e.fuel_kg, e.track_progress, e.elapsed_race_seconds) for e in stopped] == [
        (e.fuel_kg, e.track_progress, e.elapsed_race_seconds) for e in previous
    ]
    assert repository.status == "stopped" and len(repository.results) == 2


def test_physical_worker_pause_and_resume_preserve_race_progress() -> None:
    """O worker mantém carros e relógio imóveis até receber retomada."""
    from test_physical_stream import CapturePublisher

    from racestream.application.physical_worker import PhysicalWorker
    from racestream.domain.physical import PhysicalRace
    from racestream.infrastructure.track_config import load_track

    repository = ControlledRepository()
    publisher = CapturePublisher()
    worker = PhysicalWorker(
        repository, repository, publisher, load_track(), time_scale=2
    )
    repository.request_start(RaceConfiguration("worker-pausa", target_laps=10))
    worker.step(0)
    worker.step(1)
    assert isinstance(worker.race, PhysicalRace)
    state = [car.distance for car in worker.race.cars]
    clock = worker.race.time
    repository.request_pause("worker-pausa")
    worker.step(5)
    assert worker.race.paused
    assert worker.race.time == clock
    assert [car.distance for car in worker.race.cars] == state
    assert publisher.events[-1]["race_status"] == "paused"
    assert publisher.events[-1]["speed_kmh"] == 0
    repository.request_resume("worker-pausa")
    worker.step(0.1)
    assert not worker.race.paused
    assert worker.race.time > clock


def test_cancel_pending_and_natural_finish() -> None:
    """Uma solicitação cancelada não roda; a conclusão natural volta à espera."""
    repository = ControlledRepository()
    publisher = InMemoryPublisher()
    worker = RaceWorker(repository, repository, publisher)
    repository.request_start(RaceConfiguration(race_id="cancelada"))
    repository.request_stop("cancelada")
    worker.step(0.1)
    assert not publisher.events
    repository.request_start(RaceConfiguration(race_id="curta", duration_seconds=0.2))
    worker.step(0.1)
    worker.step(0.2)
    assert repository.status == "finished"
    assert len(repository.results) == 2
    assert worker.active_race_id is None
    assert publisher.events[-1].race_status == "finished"


def test_failed_initial_publication_releases_claimed_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma falha depois da reserva pode ser registrada e libera o worker."""
    repository = ControlledRepository()
    publisher = InMemoryPublisher()
    worker = RaceWorker(repository, repository, publisher)
    repository.request_start(RaceConfiguration(race_id="falha"))
    monkeypatch.setattr(
        publisher, "publish", lambda event: (_ for _ in ()).throw(RuntimeError("falha"))
    )
    with pytest.raises(RuntimeError):
        worker.step(0.1)
    worker.fail_active()
    assert repository.status == "failed" and worker.active_race_id is None


def test_api_start_is_idempotent_and_stop_reports_missing_race() -> None:
    """Os endpoints aceitam início e parada e retornam 404 para ID inexistente."""
    repository = ControlledRepository()
    with TestClient(create_app(repository, FakeTelemetryHub(), repository)) as client:
        first = client.post("/api/races/start")
        second = client.post("/api/races/start")
        assert first.status_code == 200
        assert first.json()["status"] == "queued"
        assert second.json()["race_id"] == first.json()["race_id"]
        stopped = client.post(f"/api/races/{first.json()['race_id']}/stop")
        assert stopped.json()["status"] == "stopped"
        assert client.post("/api/races/inexistente/stop").status_code == 404


def test_api_start_persists_weather_and_incident_scenarios() -> None:
    """A API valida e encaminha os cenários configurados para a largada."""
    repository = ControlledRepository()

    app = create_app(repository, FakeTelemetryHub(), repository)
    endpoint = next(
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/races/start"
    )
    endpoint(
        RaceStartRequest(
            rain_enabled=True,
            rain_start_lap=3,
            rain_intensity=0.75,
            incidents=[
                IncidentRequest(
                    incident_type="tire_puncture",
                    lap=4,
                    car_id=repository.configurations[0].car_id,
                ),
                IncidentRequest(
                    incident_type="time_penalty",
                    lap=5,
                    car_id=repository.configurations[1].car_id,
                    penalty_seconds=10,
                ),
            ],
        )
    )

    assert repository.configuration is not None
    assert repository.configuration.rain_enabled
    assert repository.configuration.rain_start_lap == 3
    assert repository.configuration.rain_intensity == 0.75
    assert repository.configuration.incidents[0].incident_type == "tire_puncture"
    assert repository.configuration.incidents[1].penalty_seconds == 10
    with pytest.raises(ValueError, match="ao menos um segundo"):
        IncidentRequest(
            incident_type="time_penalty",
            lap=5,
            car_id=repository.configurations[0].car_id,
        )
    with pytest.raises(HTTPException) as error:
        endpoint(
            RaceStartRequest(
                rain_enabled=True,
                rain_start_lap=58,
                rain_intensity=0.5,
            )
        )
    assert error.value.status_code == 422
    assert "até a volta 57" in str(error.value.detail)


def test_api_rejects_events_after_a_collision_retires_the_car() -> None:
    """Carros envolvidos em colisão não participam de eventos posteriores."""
    repository = ControlledRepository()
    endpoint = next(
        route.endpoint
        for route in create_app(repository, FakeTelemetryHub(), repository).routes
        if isinstance(route, APIRoute) and route.path == "/api/races/start"
    )

    with pytest.raises(HTTPException) as error:
        endpoint(
            RaceStartRequest(
                incidents=[
                    IncidentRequest(
                        incident_type="collision",
                        lap=15,
                        car_id=repository.configurations[0].car_id,
                        second_car_id=repository.configurations[1].car_id,
                    ),
                    IncidentRequest(
                        incident_type="tire_puncture",
                        lap=16,
                        car_id=repository.configurations[0].car_id,
                    ),
                ]
            )
        )

    assert error.value.status_code == 422
    assert "já retirado(s)" in str(error.value.detail)


def test_api_accepts_wet_tire_and_rejects_rain_on_last_lap() -> None:
    """O setup aceita composto molhado e a chuva precisa permitir a parada."""
    setup = CarConfigurationRequest(
        driver_id="DRV-01",
        car_weight_kg=830,
        driver_weight_kg=76,
        top_speed_kmh=340,
        tire_compound="wet",
    )
    assert setup.tire_compound == "wet"
    with pytest.raises(ValueError, match="antes da última volta"):
        RaceStartRequest(rain_enabled=True, rain_start_lap=60)
