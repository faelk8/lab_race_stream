"""Deterministic race and vehicle simulation."""

from datetime import UTC, datetime
from math import floor
from random import Random

from racestream.domain.models import CarState, TelemetryEvent, TireCompound

CAR_COUNT = 20
TRACK_LENGTH_M = 5_000.0


class RaceSimulator:
    """Advance independent cars and produce telemetry snapshots."""

    def __init__(
        self,
        seed: int,
        race_id: str = "race-local-001",
        car_count: int = CAR_COUNT,
        track_length_m: float = TRACK_LENGTH_M,
    ) -> None:
        """Initialize cars with independent random generators.

        :param seed: Seed used to make simulation behavior reproducible.
        :param race_id: Identifier shared by events from this race.
        :param car_count: Number of cars to simulate.
        :param track_length_m: Length of one lap in meters.
        :raises ValueError: If car count or track length is not positive.
        """
        if car_count < 1:
            raise ValueError("car_count must be positive")
        if track_length_m <= 0:
            raise ValueError("track_length_m must be positive")

        self.race_id = race_id
        self.track_length_m = track_length_m
        seed_generator = Random(seed)
        self._random_by_car: dict[str, Random] = {}
        self.cars: list[CarState] = []
        for index in range(1, car_count + 1):
            car_id = f"CAR-{index:02d}"
            self._random_by_car[car_id] = Random(seed_generator.getrandbits(64))
            self.cars.append(
                CarState(
                    car_id=car_id,
                    driver_id=f"DRV-{index:02d}",
                    speed_kmh=0.0,
                    gear=1,
                    rpm=1_000,
                    fuel_kg=110.0,
                    lap=1,
                    sector=1,
                    track_progress=0.0,
                    race_position=index,
                    throttle=0.0,
                    brake=0.0,
                    tire_compound=(
                        TireCompound.SOFT,
                        TireCompound.MEDIUM,
                        TireCompound.HARD,
                    )[(index - 1) % 3],
                    tire_age_laps=0,
                    pit_status="on_track",
                )
            )

    def tick(self, elapsed_seconds: float = 1.0) -> tuple[TelemetryEvent, ...]:
        """Advance all cars and return their telemetry snapshots.

        :param elapsed_seconds: Simulated time elapsed since the last tick.
        :return: One telemetry event per car, ordered by car identifier.
        :raises ValueError: If elapsed time is not positive.
        """
        if elapsed_seconds <= 0:
            raise ValueError("elapsed_seconds must be positive")

        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        for car in self.cars:
            self._advance_car(car, elapsed_seconds)
        self._update_race_positions()
        return tuple(self._to_event(car, now) for car in self.cars)

    def _advance_car(self, car: CarState, elapsed_seconds: float) -> None:
        """Advance one car using its independent random generator."""
        random = self._random_by_car[car.car_id]
        car.brake = random.uniform(0.0, 0.35) if car.speed_kmh > 300 else 0.0
        if random.random() < 0.025:
            car.brake = random.uniform(0.1, 0.45)
        car.throttle = 0.0 if car.brake else random.uniform(0.55, 1.0)

        acceleration = car.throttle * 9.0 - car.brake * 24.0
        car.speed_kmh = min(
            340.0,
            max(0.0, car.speed_kmh + acceleration * elapsed_seconds),
        )
        car.gear = min(8, max(1, int(car.speed_kmh // 42.0) + 1))
        car.rpm = min(15_000, 1_000 + int((car.speed_kmh % 42.0) / 42.0 * 5_000))

        fuel_consumption = (
            0.0005 + car.throttle * 0.0012 + car.speed_kmh / 340.0 * 0.0005
        ) * elapsed_seconds
        car.fuel_kg = max(0.0, car.fuel_kg - fuel_consumption)

        progress = car.track_progress + (
            car.speed_kmh / 3.6 * elapsed_seconds / self.track_length_m
        )
        completed_laps = floor(progress)
        if completed_laps:
            car.lap += completed_laps
            car.tire_age_laps += completed_laps
        car.track_progress = progress % 1.0
        car.sector = min(3, int(car.track_progress * 3) + 1)

    def _update_race_positions(self) -> None:
        """Rank cars by completed distance, breaking ties by car identifier."""
        ordered_cars = sorted(
            self.cars,
            key=lambda car: (car.lap + car.track_progress, car.car_id),
            reverse=True,
        )
        for position, car in enumerate(ordered_cars, start=1):
            car.race_position = position

    def _to_event(self, car: CarState, event_time: str) -> TelemetryEvent:
        """Create an immutable event from the current state of one car."""
        car.telemetry_sequence += 1
        return TelemetryEvent(
            event_id=f"{self.race_id}:{car.car_id}:{car.telemetry_sequence}",
            event_type="race.telemetry.v1",
            schema_version=1,
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
        )