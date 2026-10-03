"""Deterministic race and vehicle simulation."""

from collections.abc import Sequence
from datetime import UTC, datetime
from math import floor
from random import Random

from racestream.domain.models import (
    BASE_LAP_TIME_MS,
    CarConfiguration,
    CarState,
    RaceConfiguration,
    TelemetryEvent,
    TireCompound,
)

CAR_COUNT = 20
TRACK_LENGTH_M = 4_309.0
RACE_DURATION_SECONDS = 120.0
TARGET_LAPS = 60
CAR_MIN_SPACING_M = 60.0
CORNER_SPEED_KMH = 155.0
BRAKING_DECELERATION_M_S2 = 12.0
BRAKING_BUFFER_M = 28.0
ACCELERATION_KMH_PER_SECOND = 65.0
BRAKING_KMH_PER_SECOND = 105.0
CURVE_ZONES = (
    (0.06, 0.10),
    (0.20, 0.24),
    (0.34, 0.40),
    (0.48, 0.53),
    (0.57, 0.62),
    (0.68, 0.74),
    (0.82, 0.87),
    (0.94, 0.98),
)


def create_default_car_configurations(
    car_count: int = CAR_COUNT,
) -> tuple[CarConfiguration, ...]:
    """Create varied, repeatable vehicle and driver configurations.

    :param car_count: Number of car profiles to create.
    :return: Immutable profiles with varied mass, top speed, and tires.
    :raises ValueError: If car count is not positive.
    """
    if car_count < 1:
        raise ValueError("car_count must be positive")

    compounds = (TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD)
    return tuple(
        CarConfiguration(
            car_id=f"CAR-{index:02d}",
            driver_id=f"DRV-{index:02d}",
            car_weight_kg=812.0 + ((index * 7) % 9) * 4.0,
            driver_weight_kg=63.0 + ((index * 11) % 16) * 2.0,
            top_speed_kmh=321.0 + ((index * 13) % 20),
            tire_compound=compounds[(index - 1) % len(compounds)],
        )
        for index in range(1, car_count + 1)
    )


class RaceSimulator:
    """Advance independent cars and produce telemetry snapshots."""

    def __init__(
        self,
        seed: int,
        race_id: str = "race-local-001",
        car_count: int = CAR_COUNT,
        track_length_m: float = TRACK_LENGTH_M,
        race_duration_seconds: float = RACE_DURATION_SECONDS,
        target_laps: int = TARGET_LAPS,
        car_configurations: Sequence[CarConfiguration] | None = None,
    ) -> None:
        """Initialize a timed race with independent car state and randomness.

        :param seed: Seed used to make simulation behavior reproducible.
        :param race_id: Identifier shared by events from this race.
        :param car_count: Number of cars to simulate.
        :param track_length_m: Length of one lap in meters.
        :param race_duration_seconds: Wall-clock duration of the compressed race.
        :param target_laps: Number of reference laps represented by the race.
        :param car_configurations: Optional persisted car setup profiles.
        :raises ValueError: If race dimensions or car configurations are invalid.
        """
        configurations = tuple(
            car_configurations or create_default_car_configurations(car_count)
        )
        if not configurations:
            raise ValueError("at least one car configuration is required")
        if race_duration_seconds <= 0 or target_laps < 1 or track_length_m <= 0:
            raise ValueError(
                "race duration, target laps, and track length must be positive"
            )
        car_ids = [configuration.car_id for configuration in configurations]
        if len(car_ids) != len(set(car_ids)):
            raise ValueError("car identifiers must be unique")

        self.configuration = RaceConfiguration(
            race_id=race_id,
            duration_seconds=race_duration_seconds,
            target_laps=target_laps,
            track_length_m=track_length_m,
        )
        self.race_id = race_id
        self.track_length_m = track_length_m
        self.race_elapsed_seconds = 0.0
        self.race_status = "running"
        seed_generator = Random(seed)
        self._random_by_car: dict[str, Random] = {}
        self.cars: list[CarState] = []
        for index, configuration in enumerate(configurations, start=1):
            car_id = configuration.car_id
            self._random_by_car[car_id] = Random(seed_generator.getrandbits(64))
            self.cars.append(
                CarState(
                    car_id=car_id,
                    driver_id=configuration.driver_id,
                    speed_kmh=0.0,
                    gear=1,
                    rpm=1_000,
                    fuel_kg=110.0,
                    lap=1,
                    sector=1,
                    track_progress=(index - 1)
                    * CAR_MIN_SPACING_M
                    / track_length_m,
                    race_position=index,
                    throttle=0.0,
                    brake=0.0,
                    tire_compound=configuration.tire_compound,
                    tire_age_laps=0,
                    pit_status="on_track",
                    configuration=configuration,
                )
            )

    def tick(self, elapsed_seconds: float = 1.0) -> tuple[TelemetryEvent, ...]:
        """Advance the compressed race clock and return telemetry snapshots.

        :param elapsed_seconds: Wall-clock time elapsed since the last tick.
        :return: One telemetry event per car, ordered by car identifier.
        :raises ValueError: If elapsed time is not positive.
        :raises RuntimeError: If the race has already finished.
        """
        if elapsed_seconds <= 0:
            raise ValueError("elapsed_seconds must be positive")
        if self.race_status == "finished":
            raise RuntimeError("race has already finished")

        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        remaining = self.configuration.duration_seconds - self.race_elapsed_seconds
        race_step = min(elapsed_seconds, remaining)
        for car in self.cars:
            self._advance_car(car, race_step)
            self._advance_progress(car, race_step)
        self._enforce_minimum_spacing()
        self.race_elapsed_seconds += race_step
        if self.race_elapsed_seconds >= self.configuration.duration_seconds:
            self.race_status = "finished"
        self._update_race_positions()
        return tuple(self._to_event(car, now) for car in self.cars)

    def _advance_car(self, car: CarState, elapsed_seconds: float) -> None:
        """Brake for corners, downshift, and accelerate up to configured top speed."""
        random = self._random_by_car[car.car_id]
        car.driving_phase = self._driving_phase(car)
        if car.driving_phase != "straight":
            car.throttle = 0.0
            if car.speed_kmh > CORNER_SPEED_KMH:
                car.brake = min(
                    1.0,
                    BRAKING_KMH_PER_SECOND
                    / max(BRAKING_KMH_PER_SECOND, car.speed_kmh - CORNER_SPEED_KMH),
                )
                car.speed_kmh = max(
                    CORNER_SPEED_KMH,
                    car.speed_kmh - BRAKING_KMH_PER_SECOND * elapsed_seconds,
                )
            else:
                car.brake = 0.0
        else:
            car.brake = 0.0
            if car.speed_kmh >= car.configuration.top_speed_kmh:
                car.speed_kmh = car.configuration.top_speed_kmh
                car.throttle = 0.0
            else:
                car.throttle = random.uniform(0.82, 1.0)
                car.speed_kmh = min(
                    car.configuration.top_speed_kmh,
                    car.speed_kmh
                    + ACCELERATION_KMH_PER_SECOND * car.throttle * elapsed_seconds,
                )
                if car.speed_kmh >= car.configuration.top_speed_kmh:
                    car.throttle = 0.0

        car.gear = min(8, max(1, int(car.speed_kmh // 42.0) + 1))
        car.rpm = min(15_000, 1_000 + int((car.speed_kmh % 42.0) / 42.0 * 5_000))

    def _driving_phase(self, car: CarState) -> str:
        """Classify the track section and detect when braking should begin."""
        progress = car.track_progress % 1.0
        if any(start <= progress < end for start, end in CURVE_ZONES):
            return "corner"
        if car.speed_kmh <= CORNER_SPEED_KMH:
            return "straight"

        speed_m_s = car.speed_kmh / 3.6
        corner_speed_m_s = CORNER_SPEED_KMH / 3.6
        braking_distance_m = (
            (speed_m_s**2 - corner_speed_m_s**2)
            / (2.0 * BRAKING_DECELERATION_M_S2)
        ) + BRAKING_BUFFER_M
        distance_to_curve_m = self._distance_to_next_curve_m(progress)
        return "braking" if distance_to_curve_m <= braking_distance_m else "straight"

    def _distance_to_next_curve_m(self, progress: float) -> float:
        """Return forward distance to the next configured corner entry."""
        curve_entries = [start for start, _ in CURVE_ZONES]
        next_entry = next((entry for entry in curve_entries if entry > progress), None)
        if next_entry is None:
            next_entry = curve_entries[0] + 1.0
        return (next_entry - progress) * self.track_length_m

    def _advance_progress(self, car: CarState, elapsed_seconds: float) -> None:
        """Advance lap progress independently from compressed physical speed."""
        lap_time_ms = car.lap_time_ms
        lap_fraction = (
            elapsed_seconds
            * self.configuration.target_laps
            / self.configuration.duration_seconds
            * BASE_LAP_TIME_MS
            / lap_time_ms
        )
        progress = car.track_progress + lap_fraction
        completed_laps = floor(progress)
        if completed_laps:
            car.lap += completed_laps
            car.tire_age_laps += completed_laps
            car.last_lap_time_ms = lap_time_ms
            if car.best_lap_time_ms is None or lap_time_ms < car.best_lap_time_ms:
                car.best_lap_time_ms = lap_time_ms
        car.track_progress = progress % 1.0
        car.sector = min(3, int(car.track_progress * 3) + 1)
        car.fuel_kg = max(0.0, car.fuel_kg - lap_fraction * 1.2)

    def _enforce_minimum_spacing(self) -> None:
        """Keep cars at least one visual car gap apart on the racing line."""
        ordered_cars = sorted(
            self.cars,
            key=lambda car: (-(car.lap - 1 + car.track_progress), car.car_id),
        )
        minimum_gap = CAR_MIN_SPACING_M / self.track_length_m
        ahead_progress: float | None = None
        for car in ordered_cars:
            progress = car.lap - 1 + car.track_progress
            if ahead_progress is not None and ahead_progress - progress < minimum_gap:
                progress = ahead_progress - minimum_gap
                car.lap = floor(progress) + 1
                car.track_progress = progress % 1.0
                car.sector = min(3, int(car.track_progress * 3) + 1)
            ahead_progress = progress

    def _update_race_positions(self) -> None:
        """Rank cars by completed distance, breaking ties by car identifier."""
        ordered_cars = sorted(
            self.cars,
            key=lambda car: (-(car.lap + car.track_progress), car.car_id),
        )
        for position, car in enumerate(ordered_cars, start=1):
            car.race_position = position

    def _to_event(self, car: CarState, event_time: str) -> TelemetryEvent:
        """Create an immutable event from the current state of one car."""
        car.telemetry_sequence += 1
        return TelemetryEvent(
            event_id=f"{self.race_id}:{car.car_id}:{car.telemetry_sequence}",
            event_type="race.telemetry.v2",
            schema_version=2,
            event_time=event_time,
            produced_at=event_time,
            race_id=self.race_id,
            car_id=car.car_id,
            driver_id=car.driver_id,
            speed_kmh=round(car.speed_kmh, 3),
            gear=car.gear,
            rpm=car.rpm,
            fuel_kg=round(car.fuel_kg, 3),
            car_weight_kg=round(car.car_weight_kg, 3),
            lap=car.lap,
            sector=car.sector,
            lap_distance_m=round(car.track_progress * self.track_length_m, 3),
            track_progress=round(car.track_progress, 6),
            race_position=car.race_position,
            throttle=round(car.throttle, 3),
            brake=round(car.brake, 3),
            tire_compound=car.tire_compound.value,
            tire_age_laps=car.tire_age_laps,
            pit_status=car.pit_status,
            driving_phase=car.driving_phase,
            current_lap_time_ms=round(car.track_progress * car.lap_time_ms),
            last_lap_time_ms=car.last_lap_time_ms,
            best_lap_time_ms=car.best_lap_time_ms,
            elapsed_race_seconds=round(self.race_elapsed_seconds, 3),
            target_laps=self.configuration.target_laps,
            race_status=self.race_status,
        )