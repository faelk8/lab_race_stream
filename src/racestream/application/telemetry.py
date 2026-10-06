"""Validation and mapping for telemetry events at service boundaries."""

from dataclasses import asdict
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from racestream.domain.models import TelemetryEvent


class TelemetryPayload(BaseModel):
    """Validated version-one telemetry contract used by Kafka adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: Literal["race.telemetry.v3"]
    schema_version: Literal[3]
    event_time: datetime
    produced_at: datetime
    race_id: str = Field(min_length=1)
    car_id: str = Field(min_length=1)
    driver_id: str = Field(min_length=1)
    speed_kmh: float = Field(ge=0.0, le=380.0)
    gear: int = Field(ge=1, le=8)
    rpm: int = Field(ge=0, le=15_000)
    fuel_kg: float = Field(ge=0.0)
    car_weight_kg: float = Field(ge=495.0)
    lap: int = Field(ge=1)
    sector: int = Field(ge=1, le=3)
    lap_distance_m: float = Field(ge=0.0)
    track_progress: float = Field(ge=0.0, lt=1.0)
    race_position: int = Field(ge=1)
    throttle: float = Field(ge=0.0, le=1.0)
    brake: float = Field(ge=0.0, le=1.0)
    tire_compound: Literal["soft", "medium", "hard", "wet"]
    tire_age_laps: int = Field(ge=0)
    pit_status: Literal["on_track", "pit_lane", "in_pit", "out_of_fuel", "tire_burst"]
    driving_phase: Literal["straight", "braking", "corner"]
    current_lap_time_ms: int = Field(ge=0)
    last_lap_time_ms: int | None = Field(default=None, ge=0)
    best_lap_time_ms: int | None = Field(default=None, ge=0)
    elapsed_race_seconds: float = Field(ge=0.0, le=120.0)
    target_laps: int = Field(ge=1)
    race_status: Literal["running", "finished", "stopped"]
    tire_pressure_psi: float = Field(default=38.0, ge=0.0)
    pit_stops: int = Field(default=0, ge=0)
    overtaking_lane: int = Field(default=0, ge=0, le=1)


def telemetry_to_payload(event: TelemetryEvent) -> dict[str, object]:
    """Validate and convert a domain event to a JSON-compatible payload.

    :param event: Immutable domain telemetry event.
    :return: Validated payload ready for Avro serialization.
    """
    payload = TelemetryPayload.model_validate(asdict(event))
    return payload.model_dump(mode="json")
