"""Domain models for cars and immutable telemetry events."""

from dataclasses import dataclass
from enum import StrEnum


class TireCompound(StrEnum):
    """Available tire compounds in the simulator."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class CarState:
    """Mutable state owned by one simulated car."""

    car_id: str
    driver_id: str
    speed_kmh: float
    gear: int
    rpm: int
    fuel_kg: float
    lap: int
    sector: int
    track_progress: float
    race_position: int
    throttle: float
    brake: float
    tire_compound: TireCompound
    tire_age_laps: int
    pit_status: str
    telemetry_sequence: int = 0

    @property
    def car_weight_kg(self) -> float:
        """Return dry vehicle weight plus the remaining fuel."""
        return 798.0 + self.fuel_kg


@dataclass(frozen=True)
class TelemetryEvent:
    """Immutable telemetry snapshot published for one car."""

    event_id: str
    event_type: str
    schema_version: int
    event_time: str
    produced_at: str
    race_id: str
    car_id: str
    driver_id: str
    speed_kmh: float
    gear: int
    rpm: int
    fuel_kg: float
    car_weight_kg: float
    lap: int
    sector: int
    lap_distance_m: float
    track_progress: float
    race_position: int
    throttle: float
    brake: float
    tire_compound: str
    tire_age_laps: int
    pit_status: str