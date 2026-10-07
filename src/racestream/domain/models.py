"""Domain models for cars and immutable telemetry events."""

from dataclasses import dataclass
from enum import StrEnum

BASE_LAP_TIME_MS = 90_000
TIRE_LAP_DELTA_MS = {
    "soft": -250,
    "medium": 0,
    "hard": 300,
    "wet": 0,
}


class TireCompound(StrEnum):
    """Available tire compounds in the simulator."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    WET = "wet"


@dataclass(frozen=True)
class CarConfiguration:
    """Configurable performance profile for one car and its driver."""

    car_id: str
    driver_id: str
    car_weight_kg: float
    driver_weight_kg: float
    top_speed_kmh: float
    tire_compound: TireCompound
    team_id: str = "TEAM-A-01"
    team_category: str = "A"
    driver_height_m: float = 1.75
    strategy: str = "A"
    pit_service_seconds: float = 3.0
    car_length_m: float = 3.0
    driver_name: str = ""
    driver_country_code: str = ""


@dataclass(frozen=True)
class RaceRules:
    """Regras educacionais versionadas da corrida e suas unidades físicas."""

    tank_capacity_kg: float = 110.0
    fuel_tanks_per_race: float = 2.0
    initial_tire_pressure_psi: float = 38.0
    burst_pressure_psi: float = 40.0
    pressure_gain_per_lap: float = 0.02
    max_overtakes: int = 12
    weight_speed_penalty_per_kg: float = 0.00008
    max_step_seconds: float = 0.01
    strategy_c_extra_stop: bool = True
    strategy_c_reserve_laps: float = 1.0


@dataclass(frozen=True)
class RaceIncident:
    """Incidente determinístico configurado para uma volta da prova.

    :param incident_type: Tipo de incidente programado.
    :param lap: Volta em que o incidente acontece.
    :param car_id: Primeiro carro envolvido.
    :param second_car_id: Segundo carro, usado em colisões.
    :param penalty_seconds: Acréscimo aplicado ao tempo final do carro.
    """

    incident_type: str
    lap: int
    car_id: str
    second_car_id: str = ""
    penalty_seconds: int = 0


@dataclass(frozen=True)
class RaceConfiguration:
    """Regras, clima e incidentes configurados para uma prova."""

    race_id: str
    duration_seconds: float = 120.0
    target_laps: int = 60
    track_length_m: float = 4_309.0
    circuit_name: str = "Autódromo José Carlos Pace"
    rain_enabled: bool = False
    rain_start_lap: int = 1
    rain_intensity: float = 0.5
    incidents: tuple[RaceIncident, ...] = ()


@dataclass(frozen=True)
class RaceSnapshot:
    """Resumo persistido do ciclo de vida e cenários de uma prova."""

    race_id: str
    circuit_name: str
    duration_seconds: float
    target_laps: int
    status: str
    started_at: str
    finished_at: str | None
    rain_enabled: bool = False
    rain_start_lap: int = 1
    rain_intensity: float = 0.5
    incidents: tuple[RaceIncident, ...] = ()


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
    pit_stops: int = 0
    pit_remaining_seconds: float = 0.0
    pending_fuel_kg: float = 0.0
    fuel_consumed_kg: float = 0.0
    tire_pressure_psi: float = 38.0
    distance_laps: float = 0.0
    retired: bool = False
    overtaking_lane: int = 0

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
    tire_pressure_psi: float = 38.0
    pit_stops: int = 0
    overtaking_lane: int = 0


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

    weight_delta_ms = (configuration.car_weight_kg - 820.0) * 4.0 + (
        configuration.driver_weight_kg - 75.0
    ) * 3.0
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
