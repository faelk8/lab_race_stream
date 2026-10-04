"""FastAPI REST and WebSocket interface for the race dashboard."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from racestream.application.event_contracts import TOPICS
from racestream.application.ports import RaceControl, RaceRepository
from racestream.domain.models import CarConfiguration, RaceConfiguration, TireCompound
from racestream.domain.simulator import RACE_DURATION_SECONDS, TARGET_LAPS
from racestream.infrastructure.postgres_repository import PostgresRaceRepository
from racestream.infrastructure.projection_store import ProjectionStore
from racestream.infrastructure.track_config import load_track
from racestream.interfaces.kafka_hub import KafkaTelemetryHub
from racestream.interfaces.logging_config import configure_logging


class CarConfigurationRequest(BaseModel):
    """Validated editable setup for one car."""

    driver_id: str = Field(min_length=1, max_length=64)
    car_weight_kg: float = Field(ge=450.0, le=1_000.0)
    driver_weight_kg: float = Field(ge=45.0, le=150.0)
    top_speed_kmh: float = Field(ge=250.0, le=380.0)
    tire_compound: Literal["soft", "medium", "hard"]
    team_id: str = Field(default="TEAM-A-01", min_length=1, max_length=64)
    team_category: Literal["A", "B", "C"] = "A"
    driver_height_m: float = Field(default=1.75, ge=1.60, le=1.90)
    strategy: Literal["A", "B", "C"] = "A"
    pit_service_seconds: float = Field(default=3.0, ge=3.0, le=6.0)
    car_length_m: float = Field(default=3.0, ge=3.0, le=3.0)
    driver_name: str = Field(default="", max_length=100)
    driver_country_code: str = Field(default="", pattern=r"^([A-Z]{2})?$")


def create_app(
    repository: RaceRepository | None = None,
    telemetry_hub: KafkaTelemetryHub | None = None,
    race_control: RaceControl | None = None,
) -> FastAPI:
    """Compose REST and WebSocket routes with injected infrastructure ports.

    :param repository: Optional race repository for tests or alternate adapters.
    :param telemetry_hub: Optional Kafka telemetry fanout adapter.
    :param race_control: Porta opcional para os comandos de início e parada.
    :return: Configured FastAPI application.
    """
    configure_logging()
    race_repository = repository or PostgresRaceRepository(
        os.environ.get(
            "DATABASE_URL",
            "postgresql://racestream:racestream@localhost:5432/racestream",
        )
    )
    control = race_control or cast(RaceControl, race_repository)
    hub = telemetry_hub or KafkaTelemetryHub()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        race_repository.seed_default_cars()
        hub.start(asyncio.get_running_loop())
        yield
        hub.stop()

    app = FastAPI(title="RaceStream Interlagos Dashboard API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a lightweight API liveness response."""
        return {"status": "ok"}

    @app.get("/api/cars")
    def list_cars() -> list[dict[str, object]]:
        """List persisted car configurations for the dashboard."""
        return [
            {
                **asdict(configuration),
                "tire_compound": configuration.tire_compound.value,
            }
            for configuration in race_repository.list_car_configurations()
        ]

    @app.put("/api/cars/{car_id}")
    def update_car(
        car_id: str,
        request: CarConfigurationRequest,
    ) -> dict[str, object]:
        """Persist a car setup that will be applied to the next race.

        :param car_id: Existing car identifier.
        :param request: Validated performance configuration.
        :return: Persisted car setup.
        """
        existing = next(
            (
                item
                for item in race_repository.list_car_configurations()
                if item.car_id == car_id
            ),
            None,
        )
        if existing is None:
            raise HTTPException(
                status_code=404, detail=f"car_id desconhecido: {car_id}"
            )
        configuration = CarConfiguration(
            car_id=car_id,
            driver_id=request.driver_id,
            car_weight_kg=request.car_weight_kg,
            driver_weight_kg=request.driver_weight_kg,
            top_speed_kmh=request.top_speed_kmh,
            tire_compound=TireCompound(request.tire_compound),
            **{
                field: getattr(request, field)
                if field in request.model_fields_set
                else getattr(existing, field)
                for field in (
                    "team_id",
                    "team_category",
                    "driver_height_m",
                    "strategy",
                    "pit_service_seconds",
                    "car_length_m",
                    "driver_name",
                    "driver_country_code",
                )
            },
        )
        try:
            saved = race_repository.save_car_configuration(configuration)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {**asdict(saved), "tire_compound": saved.tire_compound.value}

    @app.post("/api/races/start")
    def start_race() -> dict[str, object]:
        """Solicite uma nova corrida ou retorne a corrida ativa existente.

        :return: Estado persistido da corrida solicitada.
        """
        configuration = RaceConfiguration(
            race_id=f"race-{uuid4().hex[:12]}",
            duration_seconds=float(
                os.environ.get("RACE_DURATION_SECONDS", str(RACE_DURATION_SECONDS))
            ),
            target_laps=int(os.environ.get("RACE_TARGET_LAPS", str(TARGET_LAPS))),
        )
        return asdict(control.request_start(configuration))

    @app.post("/api/races/{race_id}/stop")
    def stop_race(race_id: str) -> dict[str, object]:
        """Solicite a parada da corrida e preserve a classificação parcial.

        :param race_id: Identificador da corrida a interromper.
        :return: Estado persistido após solicitar a parada.
        """
        try:
            return asdict(control.request_stop(race_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/races/latest")
    def latest_race() -> dict[str, object] | None:
        """Return the latest persisted race lifecycle snapshot."""
        race = race_repository.get_latest_race()
        return asdict(race) if race is not None else None

    def read_projection(race_id: str) -> dict[str, Any] | None:
        """Recupere uma projeção com conexão curta e independente por requisição."""
        store = ProjectionStore(
            os.environ.get(
                "DATABASE_URL",
                "postgresql://racestream:racestream@localhost:5432/racestream",
            )
        )
        try:
            return store.snapshot(race_id)
        finally:
            store.close()

    @app.get("/api/streaming")
    def streaming_info() -> dict[str, Any]:
        """Exponha o catálogo de tópicos e a frequência de publicação."""
        return {
            "topics": TOPICS,
            "telemetry_interval_seconds": 1,
            "time_scale": float(os.environ.get("RACE_TIME_SCALE", "45")),
        }

    @app.get("/api/tracks/{track_id}")
    def track_definition(track_id: str) -> dict[str, Any]:
        """Retorne a geometria aproximada e a posição das linhas simuladas."""
        track = load_track()
        if track_id != track.track_id:
            raise HTTPException(404, "Pista desconhecida")
        return asdict(track)

    @app.get("/api/races/{race_id}/state")
    def race_state(race_id: str) -> dict[str, Any] | None:
        """Retorne estado recuperável, análises e participantes da sessão."""
        return read_projection(race_id)

    @app.get("/api/races/{race_id}/cars/{car_id}/laps")
    def car_laps(race_id: str, car_id: str) -> list[dict[str, Any]]:
        """Consulte o histórico de voltas cronometradas do carro."""
        store = ProjectionStore(os.environ["DATABASE_URL"])
        try:
            return store.history(race_id, car_id, "lap")
        finally:
            store.close()

    @app.get("/api/races/{race_id}/cars/{car_id}/splits")
    def car_splits(race_id: str, car_id: str) -> list[dict[str, Any]]:
        """Consulte todas as passagens cronometradas pela pista."""
        store = ProjectionStore(os.environ["DATABASE_URL"])
        try:
            return store.history(race_id, car_id, "timing")
        finally:
            store.close()

    @app.get("/api/races/{race_id}/teams/{team_id}/analytics")
    def team_analytics(race_id: str, team_id: str) -> list[dict[str, Any]]:
        """Compare os resumos individuais dos carros de uma equipe."""
        projection = read_projection(race_id)
        return [
            car
            for car in ((projection or {}).get("analytics") or {}).get("cars", [])
            if car["team_id"] == team_id
        ]

    @app.websocket("/ws/races/{race_id}")
    async def race_telemetry(websocket: WebSocket, race_id: str) -> None:
        """Stream the latest snapshots for one race to a browser client.

        :param websocket: Active browser WebSocket connection.
        :param race_id: Race identifier used to filter Kafka events.
        """
        await websocket.accept()
        queue = hub.subscribe()
        try:
            initial = await asyncio.to_thread(read_projection, race_id)
            if initial:
                await websocket.send_json(
                    {"kind": "snapshot", "race_id": race_id, **initial}
                )
            while True:
                event = await queue.get()
                if event.get("race_id") == race_id:
                    await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    return app


app = create_app()
