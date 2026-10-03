"""Domain models for cars and immutable telemetry events."""

from dataclasses import dataclass
from enum import StrEnum

BASE_LAP_TIME_MS = 90_000
TIRE_LAP_DELTA_MS = {
    "soft": -250,
    "medium": 0,
    "hard": 300,
}


class TireCompound(StrEnum):
    """Available tire compounds in the simulator."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class CarConfiguration:
    """Configurable performance profile for one car and its driver."""

    car_id: str
    driver_id: str
    car_weight_kg: float
    driver_weight_kg: float
    top_speed_kmh: float
    tire_compound: TireCompound


@dataclass(frozen=True)
class RaceConfiguration:
    """Timing and circuit rules for one race."""

    race_id: str
    duration_seconds: float = 120.0
    target_laps: int = 60
    track_length_m: float = 4_309.0
    circuit_name: str = "Autódromo José Carlos Pace"


@dataclass(frozen=True)
class RaceSnapshot:
    """Persisted lifecycle summary of a race."""

    race_id: str
    circuit_name: str
    duration_seconds: float
    target_laps: int
    status: str
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class RaceResult:
    """Final position and car setup snapshot for one race participant."""

    race_id: str
    car_id: str
    race_position: int
    laps_completed: int
    last_lap_time_ms: int | None
    best_lap_time_ms: int | None
    car_weight_kg: float
    driver_weight_kg: float
    top_speed_kmh: float
    tire_compound: TireCompound


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
    configuration: CarConfiguration
    driving_phase: str = "straight"
    last_lap_time_ms: int | None = None
    best_lap_time_ms: int | None = None
    telemetry_sequence: int = 0

    @property
    def car_weight_kg(self) -> float:
        """Return total car, driver, and remaining fuel weight."""
        return (
            self.configuration.car_weight_kg
            + self.configuration.driver_weight_kg
            + self.fuel_kg
        )

    @property
    def lap_time_ms(self) -> int:
        """Return configured lap time including tire wear."""
        return calculate_lap_time_ms(self.configuration, self.tire_age_laps)


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
    driving_phase: str
    current_lap_time_ms: int
    last_lap_time_ms: int | None
    best_lap_time_ms: int | None
    elapsed_race_seconds: float
    target_laps: int
    race_status: str


def calculate_lap_time_ms(
    configuration: CarConfiguration,
    tire_age_laps: int = 0,
) -> int:
    """Calculate a deterministic lap-time estimate for a car configuration.

    :param configuration: Vehicle, driver, and tire configuration.
    :param tire_age_laps: Number of laps completed on the current tire set.
    :return: Estimated lap time in milliseconds.
    :raises ValueError: If tire age is negative.
    """
    if tire_age_laps < 0:
        raise ValueError("tire_age_laps must be non-negative")

    weight_delta_ms = (
        (configuration.car_weight_kg - 820.0) * 4.0
        + (configuration.driver_weight_kg - 75.0) * 3.0
    )
    speed_delta_ms = (330.0 - configuration.top_speed_kmh) * 18.0
    tire_delta_ms = TIRE_LAP_DELTA_MS[configuration.tire_compound.value]
    tire_wear_ms = tire_age_laps * 15.0
    return max(
        60_000,
        round(
            BASE_LAP_TIME_MS
            + weight_delta_ms
            + speed_delta_ms
            + tire_delta_ms
            + tire_wear_ms
        ),
    )