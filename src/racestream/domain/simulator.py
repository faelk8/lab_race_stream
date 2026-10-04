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
    RaceRules,
    TelemetryEvent,
    TireCompound,
)

CAR_COUNT = 20
TRACK_LENGTH_M = 4_309.0
RACE_DURATION_SECONDS = 120.0
TARGET_LAPS = 60
CAR_MIN_SPACING_M = 3.0
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


# Pilotos fictícios para o grid educacional.
DEFAULT_DRIVERS = (
    ("Rafael Almeida", "BR"),
    ("Lucas Ribeiro", "BR"),
    ("Matías Silva", "AR"),
    ("Diego Torres", "AR"),
    ("João Costa", "PT"),
    ("Miguel Santos", "PT"),
    ("Oliver Bennett", "GB"),
    ("William Parker", "GB"),
    ("Matteo Rossi", "IT"),
    ("Luca Bianchi", "IT"),
    ("Alejandro García", "ES"),
    ("Carlos Medina", "ES"),
    ("Pierre Martin", "FR"),
    ("Julien Moreau", "FR"),
    ("Lukas Weber", "DE"),
    ("Maximilian Keller", "DE"),
    ("Kenji Sato", "JP"),
    ("Haruto Tanaka", "JP"),
    ("Liam Campbell", "CA"),
    ("Noah Wilson", "CA"),
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
    profiles = []
    for index in range(car_count):
        slot = index % 20
        category = "A" if slot < 8 else "B" if slot < 16 else "C"
        dry_weight, minimum_speed = {
            "A": (500.0, 290.0),
            "B": (510.0, 280.0),
            "C": (515.0, 260.0),
        }[category]
        height = round(1.60 + (slot * 7 % 31) / 100, 2)
        profiles.append(
            CarConfiguration(
                car_id=f"CAR-{index + 1:02d}",
                driver_id=f"DRV-{index + 1:02d}",
                driver_name=DEFAULT_DRIVERS[slot][0],
                driver_country_code=DEFAULT_DRIVERS[slot][1],
                car_weight_kg=dry_weight,
                driver_weight_kg=round(22.0 * height**2, 2),
                top_speed_kmh=minimum_speed + (slot * 13 % 31),
                tire_compound=compounds[index % 3],
                team_id=f"TEAM-{category}-{(slot % 8) // 2 + 1:02d}",
                team_category=category,
                driver_height_m=height,
                strategy="ABC"[index % 3],
                pit_service_seconds=3.0 + (slot // 2 % 4),
            )
        )
    return tuple(profiles)


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
        rules: RaceRules | None = None,
    ) -> None:
        """Initialize a timed race with independent car state and randomness.

        :param seed: Seed used to make simulation behavior reproducible.
        :param race_id: Identifier shared by events from this race.
        :param car_count: Number of cars to simulate.
        :param track_length_m: Length of one lap in meters.
        :param race_duration_seconds: Wall-clock duration of the compressed race.
        :param target_laps: Number of reference laps represented by the race.
        :param car_configurations: Optional persisted car setup profiles.
        :param rules: Regras versionadas de combustível, pneus, tráfego e estratégias.
        :raises ValueError: If race dimensions or car configurations are invalid.
        """
        self.rules = rules or RaceRules()
        self.overtakes = 0
        self._passing: dict[str, str] = {}
        self._counted_passes: set[str] = set()
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
                    fuel_kg=self.rules.tank_capacity_kg
                    * (1.0 if configuration.strategy == "A" else 0.5),
                    lap=1,
                    sector=1,
                    track_progress=(len(configurations) - index)
                    * CAR_MIN_SPACING_M
                    / track_length_m,
                    race_position=index,
                    throttle=0.0,
                    brake=0.0,
                    tire_compound=configuration.tire_compound,
                    tire_age_laps=0,
                    tire_pressure_psi=self.rules.initial_tire_pressure_psi,
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
        if self.race_status == "stopped":
            raise RuntimeError("A corrida está parada")

        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        remaining = self.configuration.duration_seconds - self.race_elapsed_seconds
        race_step = min(elapsed_seconds, remaining)
        remaining_step = race_step
        while remaining_step > 1e-9:
            step = min(remaining_step, self.rules.max_step_seconds)
            previous_order = sorted(self.cars, key=lambda car: car.race_position)
            proposals: dict[str, float] = {}
            for car in self.cars:
                self._advance_car(car, step)
                proposals[car.car_id] = self._proposed_progress(car, step)
            self._resolve_traffic(previous_order, proposals)
            for car in self.cars:
                self._advance_progress(car, proposals[car.car_id])
            self._update_race_positions()
            remaining_step -= step
        self.race_elapsed_seconds += race_step
        if self.race_elapsed_seconds >= self.configuration.duration_seconds:
            self.race_status = "finished"
        self._update_race_positions()
        return tuple(self._to_event(car, now) for car in self.cars)

    def snapshot(self) -> tuple[TelemetryEvent, ...]:
        """Retorne a telemetria atual sem avançar o relógio da corrida.

        :return: Eventos imutáveis dos carros no estado atual.
        """
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        return tuple(self._to_event(car, now) for car in self.cars)

    def stop(self) -> None:
        """Encerre a corrida preservando distância e classificação."""
        self.race_status = "stopped"
        for car in self.cars:
            car.speed_kmh = 0.0
            car.throttle = 0.0
            car.brake = 0.0
            car.gear = 1
            car.rpm = 1000

    def _advance_car(self, car: CarState, elapsed_seconds: float) -> None:
        """Brake for corners, downshift, and accelerate up to configured top speed."""
        if car.retired:
            car.speed_kmh = 0.0
            car.throttle = 0.0
            car.brake = 0.0
            return
        if car.pit_remaining_seconds > 0:
            car.pit_remaining_seconds = max(
                0.0,
                car.pit_remaining_seconds
                - elapsed_seconds
                * self.configuration.target_laps
                * BASE_LAP_TIME_MS
                / 1000
                / self.configuration.duration_seconds,
            )
            if car.pit_remaining_seconds < 1e-9:
                car.pit_remaining_seconds = 0.0
            car.speed_kmh = 0.0
            car.throttle = 0.0
            car.brake = 0.0
            car.gear = 1
            car.rpm = 1000
            if car.pit_remaining_seconds == 0:
                car.fuel_kg = car.pending_fuel_kg
                if car.pit_stops == 1:
                    car.tire_age_laps = 0
                    car.tire_pressure_psi = self.rules.initial_tire_pressure_psi
                car.pit_status = "on_track"
            return
        self._maybe_enter_pit(car)
        if car.retired or car.pit_status == "in_pit":
            car.speed_kmh = 0.0
            car.throttle = 0.0
            car.brake = 0.0
            return
        elapsed_seconds *= (
            self.configuration.target_laps
            * BASE_LAP_TIME_MS
            / 1000
            / self.configuration.duration_seconds
        )
        random = self._random_by_car[car.car_id]
        top_speed = car.configuration.top_speed_kmh * min(
            1.0,
            max(
                0.8,
                1.0
                - (car.car_weight_kg - (car.configuration.car_weight_kg + 56.32))
                * self.rules.weight_speed_penalty_per_kg,
            ),
        )
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
            if car.speed_kmh >= top_speed:
                car.speed_kmh = top_speed
                car.throttle = 0.0
            else:
                car.throttle = random.uniform(0.82, 1.0)
                car.speed_kmh = min(
                    top_speed,
                    car.speed_kmh
                    + ACCELERATION_KMH_PER_SECOND * car.throttle * elapsed_seconds,
                )
                if car.speed_kmh >= top_speed:
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
            (speed_m_s**2 - corner_speed_m_s**2) / (2.0 * BRAKING_DECELERATION_M_S2)
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

    def _maybe_enter_pit(self, car: CarState) -> None:
        """Abasteça conforme a estratégia selecionada, respeitando a capacidade do
        tanque.
        """
        capacity = self.rules.tank_capacity_kg
        strategy = car.configuration.strategy
        threshold = {"A": 0.0, "B": 0.1, "C": 0.2}[strategy]
        maximum_stops = 1 if strategy == "A" else 2
        if strategy == "C" and self.rules.strategy_c_extra_stop:
            maximum_stops = 3
        remaining_fuel = (
            max(0.0, self.configuration.target_laps - car.distance_laps)
            * capacity
            * self.rules.fuel_tanks_per_race
            / self.configuration.target_laps
        )
        reserve_fuel = 0.0
        if strategy == "C" and self.rules.strategy_c_extra_stop:
            reserve_fuel = (
                self.rules.strategy_c_reserve_laps
                * capacity
                * self.rules.fuel_tanks_per_race
                / self.configuration.target_laps
            )
        if remaining_fuel + reserve_fuel <= car.fuel_kg + 1e-8:
            return
        if car.fuel_kg > capacity * threshold + 1e-8:
            return
        if car.pit_stops >= maximum_stops:
            if car.fuel_kg <= 1e-8:
                car.retired = True
                car.pit_status = "out_of_fuel"
            return
        car.pit_stops += 1
        target = capacity
        if strategy == "C" and car.pit_stops == 1:
            target = capacity * 0.5
        elif car.pit_stops == maximum_stops:
            target = min(capacity, remaining_fuel + reserve_fuel)
        car.pending_fuel_kg = target
        car.pit_remaining_seconds = car.configuration.pit_service_seconds
        car.pit_status = "in_pit"

    def _proposed_progress(self, car: CarState, elapsed_seconds: float) -> float:
        """Calcule o avanço limitado pelo combustível disponível e pela distância da
        prova.
        """
        current = car.lap - 1 + car.track_progress
        if car.retired or car.pit_status == "in_pit" or car.speed_kmh == 0:
            return current
        fraction = (
            elapsed_seconds
            * self.configuration.target_laps
            / self.configuration.duration_seconds
            * BASE_LAP_TIME_MS
            / car.lap_time_ms
        )
        fraction *= 1.0 / (1.0 + car.fuel_kg * 0.00008)
        fuel_per_lap = (
            self.rules.tank_capacity_kg
            * self.rules.fuel_tanks_per_race
            / self.configuration.target_laps
        )
        return current + min(
            fraction,
            car.fuel_kg / fuel_per_lap,
            max(0.0, self.configuration.target_laps - car.distance_laps),
        )

    def _resolve_traffic(
        self,
        ordered: list[CarState],
        proposals: dict[str, float],
    ) -> None:
        """Permita ultrapassagens em duplas nas retas e limite o avanço antes de
        contabilizá-lo.
        """
        active = [
            car for car in ordered if not car.retired and car.pit_status == "on_track"
        ]
        gap = CAR_MIN_SPACING_M / self.track_length_m
        by_id = {car.car_id: car for car in self.cars}
        for behind_id, ahead_id in list(self._passing.items()):
            behind, ahead = by_id[behind_id], by_id[ahead_id]
            if (
                behind.retired
                or ahead.retired
                or (behind.pit_status != "on_track" or ahead.pit_status != "on_track")
            ):
                behind.overtaking_lane = 0
                del self._passing[behind_id]
                self._counted_passes.discard(behind_id)
                continue
            if proposals[behind_id] > proposals[ahead_id]:
                if behind_id not in self._counted_passes:
                    self.overtakes += 1
                    self._counted_passes.add(behind_id)
                if proposals[behind_id] - proposals[ahead_id] >= gap:
                    behind.overtaking_lane = 0
                    del self._passing[behind_id]
                    self._counted_passes.discard(behind_id)
        busy = set(self._passing) | set(self._passing.values())
        for ahead, behind in zip(active, active[1:], strict=False):
            reserved = len(set(self._passing) - self._counted_passes)
            if (
                behind.car_id not in busy
                and ahead.car_id not in busy
                and proposals[behind.car_id] >= proposals[ahead.car_id] - gap
                and behind.driving_phase == ahead.driving_phase == "straight"
                and behind.speed_kmh > ahead.speed_kmh
                and behind.configuration.top_speed_kmh
                > ahead.configuration.top_speed_kmh
                and self.overtakes + reserved < self.rules.max_overtakes
            ):
                self._passing[behind.car_id] = ahead.car_id
                behind.overtaking_lane = 1
                busy.update((behind.car_id, ahead.car_id))
        for lane in (0, 1):
            lane_cars = [car for car in active if car.overtaking_lane == lane]
            for ahead, behind in zip(lane_cars, lane_cars[1:], strict=False):
                current = behind.lap - 1 + behind.track_progress
                proposals[behind.car_id] = max(
                    current,
                    min(proposals[behind.car_id], proposals[ahead.car_id] - gap),
                )

    def _advance_progress(self, car: CarState, progress: float) -> None:
        """Registre o avanço aceito, as voltas, o desgaste dos pneus e o consumo por
        distância.
        """
        previous = car.lap - 1 + car.track_progress
        fraction = max(0.0, progress - previous)
        completed_laps = floor(progress) - floor(previous)
        lap_time_ms = car.lap_time_ms
        if completed_laps:
            car.tire_age_laps += completed_laps
            car.last_lap_time_ms = lap_time_ms
            if car.best_lap_time_ms is None or lap_time_ms < car.best_lap_time_ms:
                car.best_lap_time_ms = lap_time_ms
        car.lap = floor(progress) + 1
        car.track_progress = progress % 1.0
        car.distance_laps += fraction
        car.sector = min(3, int(car.track_progress * 3) + 1)
        consumed = min(
            car.fuel_kg,
            fraction
            * self.rules.tank_capacity_kg
            * self.rules.fuel_tanks_per_race
            / self.configuration.target_laps,
        )
        car.fuel_kg = max(0.0, car.fuel_kg - consumed)
        car.fuel_consumed_kg += consumed
        car.tire_pressure_psi += fraction * self.rules.pressure_gain_per_lap
        if car.tire_pressure_psi >= self.rules.burst_pressure_psi:
            car.retired = True
            car.pit_status = "tire_burst"
            car.speed_kmh = 0.0

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
            event_type="race.telemetry.v3",
            schema_version=3,
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
            tire_pressure_psi=round(car.tire_pressure_psi, 4),
            pit_stops=car.pit_stops,
            overtaking_lane=car.overtaking_lane,
        )
