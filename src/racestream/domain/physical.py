"""Simulação física com cronometragem por passagem e aceleração em g."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import floor, hypot
from random import Random
from typing import Any

from racestream.domain.models import CarConfiguration, RaceConfiguration, RaceResult
from racestream.domain.track import Track

PIT_BRAKING_USAGE = 0.5


@dataclass
class PhysicalCar:
    """Mantenha o estado independente de um participante da sessão."""

    configuration: CarConfiguration
    distance: float
    fuel: float
    active_tire: str = "medium"
    wet_stop_lap: int | None = None
    target_tire: str | None = None
    speed: float = 0.0
    position: int = 0
    lap_start: float = 0.0
    line_start: float = 0.0
    sector_start: float = 0.0
    last_lap: int | None = None
    best_lap: int | None = None
    worst_lap: int | None = None
    status: str = "racing"
    pit_status: str = "on_track"
    pit_stops: int = 0
    pit_remaining: float = 0.0
    pit_added: float = 0.0
    pit_entry_time: float | None = None
    pit_lap_number: int | None = None
    pit_requested: bool = False
    tire_change_pending: bool = False
    applied_incidents: set[int] = field(default_factory=set)
    pit_lap: bool = False
    tire_age: float = 0.0
    pressure: float = 38.0
    throttle: float = 0.0
    brake: float = 0.0
    g_long: float = 0.0
    g_lat: float = 0.0
    peak_g: float = 0.0
    g_valid: bool = True
    finished_at: float | None = None
    retired_at: float | None = None
    sequence: int = 0
    lane: int = 0
    pace: float = 1.0
    sector_times: list[int] = field(default_factory=list)


class PhysicalRace:
    """Integre movimento e emita fatos sem depender de Kafka ou de banco."""

    def __init__(
        self,
        configuration: RaceConfiguration,
        profiles: tuple[CarConfiguration, ...],
        track: Track,
        seed: int = 42,
        time_scale: float = 45,
    ) -> None:
        """Inicialize grid, relógio fixo e participantes congelados da corrida."""
        if not profiles or configuration.target_laps < 1:
            raise ValueError("A corrida precisa de carros e voltas positivas")
        self.configuration = configuration
        self.track = track
        self.time_scale = time_scale
        self.time = 0.0
        self.pending_time = 0.0
        self.status = "running"
        self.snapshot_id = 0
        self.sequence = 0
        self.overtakes = 0
        self.leader_finished: float | None = None
        self.events: list[dict[str, Any]] = []
        if (
            configuration.rain_enabled
            and configuration.rain_start_lap >= configuration.target_laps
        ):
            raise ValueError("A chuva deve começar antes da última volta")
        last_rain_stop_lap = configuration.target_laps - 1
        latest_start_lap = last_rain_stop_lap - 2 * (len(profiles) - 1)
        if (
            configuration.rain_enabled
            and configuration.rain_start_lap > latest_start_lap
        ):
            raise ValueError(
                "A chuva começa tarde demais para escalonar a troca de todos os carros"
            )
        car_ids = {profile.car_id for profile in profiles}
        for incident in configuration.incidents:
            if incident.lap > configuration.target_laps:
                raise ValueError("A volta do incidente excede o total da corrida")
            if incident.car_id not in car_ids or (
                incident.second_car_id and incident.second_car_id not in car_ids
            ):
                raise ValueError("O incidente referencia um carro inexistente")
        rain_stop_laps = self._rain_stop_schedule(len(profiles), seed)
        self.cars = [
            PhysicalCar(
                p,
                -(i // 2) * track.grid_spacing_m,
                track.tank_capacity_kg * (1.0 if p.strategy == "A" else 0.5),
                active_tire=p.tire_compound.value,
                wet_stop_lap=rain_stop_laps[i],
                position=i + 1,
                lane=i % 2,
                pace=Random(seed + i).uniform(0.97, 1.0),
            )
            for i, p in enumerate(profiles)
        ]
        self._emit(
            "control",
            {
                "status": "running",
                "target_laps": configuration.target_laps,
                "participants": [asdict(p) for p in profiles],
                "track": asdict(track),
            },
        )

    def _rain_stop_schedule(self, car_count: int, seed: int) -> list[int | None]:
        """Distribua paradas por pneus de chuva em intervalos de duas a seis voltas.

        :param car_count: Quantidade de carros inscritos.
        :param seed: Semente determinística da corrida.
        :return: Volta-alvo por carro, na ordem dos perfis recebidos.
        """
        if not self.configuration.rain_enabled:
            return [None] * car_count
        first_lap = self.configuration.rain_start_lap
        last_lap = self.configuration.target_laps - 1
        slot_count = car_count
        laps = [first_lap]
        rng = Random(seed ^ 0x5A17)
        while len(laps) < slot_count:
            laps.append(laps[-1] + rng.randint(2, 6))
        while laps[-1] > last_lap:
            candidates = [
                index
                for index in range(1, len(laps))
                if laps[index] - laps[index - 1] > 2
            ]
            if not candidates:
                laps = [first_lap + 2 * index for index in range(slot_count)]
                break
            index = candidates[-1]
            for later in range(index, len(laps)):
                laps[later] -= 1
        if laps[-1] > last_lap:
            laps = [first_lap + 2 * index for index in range(slot_count)]
        order = list(range(car_count))
        rng.shuffle(order)
        schedule: list[int | None] = [None] * car_count
        for index, car_index in enumerate(order):
            schedule[car_index] = laps[index]
        return schedule

    def _emit(
        self,
        kind: str,
        data: dict[str, Any],
        car: PhysicalCar | None = None,
        at: float | None = None,
    ) -> None:
        """Crie um fato com identidade estável para tentativas de publicação."""
        self.sequence += 1
        now = datetime.now(UTC).isoformat()
        self.events.append(
            {
                "kind": kind,
                "event_id": f"{self.configuration.race_id}:{self.sequence}",
                "race_id": self.configuration.race_id,
                "event_time": now,
                "produced_at": now,
                "simulation_time_us": round((self.time if at is None else at) * 1e6),
                "source_sequence": self.sequence,
                "track_version": self.track.version,
                "rules_version": "lab-v2",
                "schema_version": 4 if kind == "telemetry" else 1,
                "car_id": car.configuration.car_id if car else "",
                **({"time_scale": self.time_scale} if kind == "control" else {}),
                **data,
            }
        )

    def advance(self, simulation_seconds: float) -> None:
        """Avance em subpassos físicos fixos, preservando determinismo da escala."""
        if simulation_seconds < 0:
            raise ValueError("O tempo não pode retroceder")
        self.pending_time += simulation_seconds
        step = self.track.physics_step_seconds
        while self.pending_time + 1e-9 >= step and self.status == "running":
            for car in sorted(self.cars, key=lambda c: -c.distance):
                self._advance_car(car, step)
            self.time += step
            self.pending_time -= step
            self._rank()
            if self.leader_finished is not None:
                for car in self.cars:
                    if (
                        car.status == "racing"
                        and self.time - self.leader_finished
                        > self.track.finish_timeout_seconds
                    ):
                        self._retire(car, "prazo_de_chegada", self.time)
            if all(c.status != "racing" for c in self.cars):
                self.status = "finished"
                self._emit(
                    "control",
                    {
                        "status": "finished",
                        "target_laps": self.configuration.target_laps,
                        "participants": [],
                        "track": asdict(self.track),
                    },
                )

    def _advance_car(self, car: PhysicalCar, dt: float) -> None:
        """Integre um carro, registre linhas e respeite tráfego e boxes."""
        if car.status != "racing":
            return
        track = self.track
        previous = car.distance
        progress = (previous / track.length_m) % 1
        self._apply_scenarios(car, previous, progress)
        if car.status != "racing":
            return
        if car.pit_status == "in_pit":
            car.speed = car.throttle = car.brake = car.g_long = car.g_lat = 0.0
            car.g_valid = True
            remaining_before = car.pit_remaining
            car.pit_remaining -= dt
            if car.pit_remaining <= 0:
                finished_at = self.time + min(dt, max(0.0, remaining_before))
                car.fuel = min(track.tank_capacity_kg, car.fuel + car.pit_added)
                if car.target_tire is not None:
                    car.active_tire = car.target_tire
                    car.target_tire = None
                if car.pit_stops == 1 or car.tire_change_pending:
                    car.tire_age, car.pressure = 0.0, 38.0
                    car.tire_change_pending = False
                car.pit_status = "pit_lane"
                self._emit(
                    "pitstop",
                    {
                        "phase": "service_finished",
                        "stop_number": car.pit_stops,
                        "fuel_added_kg": car.pit_added,
                        "tire_compound": car.active_tire,
                        "lap": self._pit_lap(car),
                        "pit_stop_time_ms": self._pit_elapsed_ms(car, finished_at),
                    },
                    car,
                    finished_at,
                )
            return
        per_m = (
            track.tank_capacity_kg
            * track.fuel_tanks_per_reference
            / (track.fuel_reference_laps * track.length_m)
        )
        remaining_distance = max(
            0.0, self.configuration.target_laps * track.length_m - previous
        )
        threshold = {"A": 0.0, "B": 11.0, "C": 22.0}[car.configuration.strategy]
        # A precisa alcançar os boxes antes de esgotar o tanque.
        next_entry = ((track.pit_entry - progress) % 1) * track.length_m
        anticipation = (
            (next_entry + track.length_m) * per_m
            if car.configuration.strategy == "A"
            else threshold
        )
        car.pit_requested = car.pit_requested or (
            car.fuel <= max(threshold, anticipation)
            and car.fuel
            < remaining_distance * per_m
            + (per_m * track.length_m if car.configuration.strategy == "C" else 0)
        )
        maximum = {"A": 1, "B": 2, "C": 3}[car.configuration.strategy]
        if car.pit_stops >= maximum and not car.tire_change_pending:
            car.pit_requested = False
        rain_active = (
            self.configuration.rain_enabled
            and floor(previous / track.length_m) + 1
            >= self.configuration.rain_start_lap
        )
        rain_factor = self.configuration.rain_intensity if rain_active else 0.0
        current_lap = floor(previous / track.length_m) + 1
        if (
            rain_active
            and car.wet_stop_lap is not None
            and current_lap >= car.wet_stop_lap
            and car.active_tire != "wet"
        ):
            car.tire_change_pending = True
            car.target_tire = "wet"
            car.pit_requested = True
        top = (
            car.configuration.top_speed_kmh
            / 3.6
            * car.pace
            * (1 - (0.05 if car.active_tire == "wet" else 0.12) * rain_factor)
        )
        top /= 1 + (car.fuel + car.configuration.driver_weight_kg - 56) * 0.00008
        target = track.speed_limit(
            progress,
            top,
            track.tire_grip_factors[car.active_tire]
            * (1 - (0.07 if car.active_tire == "wet" else 0.25) * rain_factor),
        )
        if car.pit_status == "pit_lane":
            target = min(target, track.pit_speed_kmh / 3.6)
            if car.pit_requested:
                distance_to_box = (
                    (track.pit_box - progress) % 1
                    * track.length_m
                    * track.pit_path_ratio
                )
                target = min(
                    target,
                    (
                        2
                        * track.braking_m_s2
                        * PIT_BRAKING_USAGE
                        * max(0.0, distance_to_box)
                    )
                    ** 0.5,
                )
        elif car.pit_requested:
            target = min(
                target,
                (
                    (track.pit_speed_kmh / 3.6) ** 2
                    + 2 * track.braking_m_s2 * max(0.0, next_entry - car.speed * dt)
                )
                ** 0.5,
            )
        old_speed = car.speed
        acceleration = max(
            -track.braking_m_s2, min(track.acceleration_m_s2, (target - old_speed) / dt)
        )
        speed = max(0.0, old_speed + acceleration * dt)
        movement = (old_speed + speed) * 0.5 * dt
        path_ratio = track.pit_path_ratio if car.pit_status == "pit_lane" else 1.0
        advance = min(movement / path_ratio, car.fuel / per_m)
        ahead = next(
            (
                other
                for other in sorted(self.cars, key=lambda c: c.distance)
                if other is not car
                and other.status == "racing"
                and other.pit_status == "on_track"
                and other.distance > previous
            ),
            None,
        )
        car.lane = 0
        if (
            ahead
            and car.pit_status == "on_track"
            and previous + advance > ahead.distance - 3
        ):
            can_pass = (
                track.radius_at(progress) is None
                and speed > ahead.speed + 0.2
                and self.overtakes < track.max_overtakes
                and ahead.lane == 0
            )
            if can_pass:
                car.lane = 1
                if previous + advance > ahead.distance:
                    self.overtakes += 1
            else:
                advance = max(0.0, ahead.distance - 3 - previous)
                speed = max(0.0, 2 * advance * path_ratio / dt - old_speed)
        proposed = previous + advance
        for fraction, phase in (
            (track.pit_entry, "entry"),
            (track.pit_box, "service"),
            (track.pit_exit, "exit"),
        ):
            boundary = (floor(previous / track.length_m) + fraction) * track.length_m
            if boundary <= previous + 1e-9:
                boundary += track.length_m
            if not previous < boundary <= proposed:
                continue
            crossing_at = self.time + (boundary - previous) / (proposed - previous) * dt
            if phase == "entry" and car.pit_requested and car.pit_status == "on_track":
                car.pit_status, car.pit_lap = "pit_lane", True
                car.pit_entry_time = crossing_at
                car.pit_lap_number = floor(boundary / track.length_m) + 1
                self._emit(
                    "pitstop",
                    {
                        "phase": "entry",
                        "stop_number": car.pit_stops + 1,
                        "fuel_added_kg": 0.0,
                        "tire_compound": car.active_tire,
                        "lap": self._pit_lap(car),
                        "pit_stop_time_ms": 0,
                    },
                    car,
                    crossing_at,
                )
            elif (
                phase == "service"
                and car.pit_status == "pit_lane"
                and car.pit_requested
            ):
                proposed, speed = boundary, 0.0
                self._service(car, per_m, crossing_at)
            elif (
                phase == "exit"
                and car.pit_status == "pit_lane"
                and not car.pit_requested
            ):
                car.pit_status = "on_track"
                self._emit(
                    "pitstop",
                    {
                        "phase": "exit",
                        "stop_number": car.pit_stops,
                        "fuel_added_kg": 0.0,
                        "tire_compound": car.active_tire,
                        "lap": self._pit_lap(car),
                        "pit_stop_time_ms": self._pit_elapsed_ms(car, crossing_at),
                    },
                    car,
                    crossing_at,
                )
                car.pit_entry_time = None
                car.pit_lap_number = None
        finish = self.configuration.target_laps * track.length_m
        if self.leader_finished is not None:
            finish = (floor(previous / track.length_m) + 1) * track.length_m
        proposed = min(proposed, finish)
        car.distance = proposed
        car.fuel = max(0.0, car.fuel - (proposed - previous) * per_m)
        car.tire_age += (proposed - previous) / track.length_m
        car.pressure += (proposed - previous) / track.length_m * 0.02
        car.speed = speed
        car.throttle = max(0.0, acceleration / track.acceleration_m_s2)
        car.brake = max(0.0, -acceleration / track.braking_m_s2)
        car.g_long = (speed - old_speed) / dt / 9.80665
        radius = track.radius_at(progress)
        car.g_lat = speed**2 / radius / 9.80665 if radius else 0.0
        # Contato numérico ou parada discreta não constitui uma medida de impacto.
        car.g_valid = (
            -track.braking_m_s2 / 9.80665 - 0.01
            <= car.g_long
            <= track.acceleration_m_s2 / 9.80665 + 0.01
        )
        if car.g_valid:
            car.peak_g = max(car.peak_g, hypot(car.g_long, car.g_lat))
        self._crossings(car, previous, proposed, dt)
        if car.status == "racing" and (car.fuel <= 1e-9 or car.pressure >= 40):
            car.pit_status = "out_of_fuel" if car.fuel <= 1e-9 else "tire_burst"
            self._retire(car, car.pit_status, self.time + dt)

    def _retire(self, car: PhysicalCar, reason: str, at: float) -> None:
        """Congele o estado individual sem simular um impacto no abandono."""
        car.status, car.retired_at = "retired", at
        car.speed = car.throttle = car.brake = car.g_long = car.g_lat = 0.0
        car.g_valid = True
        car.lane = 0
        self._emit("incident", {"reason": reason}, car, at)

    def _apply_scenarios(
        self, car: PhysicalCar, distance: float, progress: float
    ) -> None:
        """Aplique incidentes programados ao alcançar a metade da volta."""
        lap = floor(distance / self.track.length_m) + 1
        if progress < 0.5:
            return
        for index, incident in enumerate(self.configuration.incidents):
            if index in car.applied_incidents or incident.lap != lap:
                continue
            if (
                incident.incident_type == "tire_puncture"
                and incident.car_id == car.configuration.car_id
            ):
                car.applied_incidents.add(index)
                car.tire_change_pending = True
                car.pit_requested = True
                self._emit("incident", {"reason": "tire_puncture"}, car)
            elif incident.incident_type == "collision" and car.configuration.car_id in (
                incident.car_id,
                incident.second_car_id,
            ):
                involved = {incident.car_id, incident.second_car_id}
                for participant in self.cars:
                    if (
                        participant.configuration.car_id in involved
                        and participant.status == "racing"
                    ):
                        participant.applied_incidents.add(index)
                        self._retire(participant, "collision", self.time)

    def _service(
        self, car: PhysicalCar, per_m: float, at: float | None = None
    ) -> None:
        """Calcule reposição por estratégia, reserva e vazão de abastecimento."""
        service_at = self.time if at is None else at
        if car.pit_entry_time is None:
            car.pit_entry_time = service_at
            car.pit_lap_number = max(
                1, floor(max(0.0, car.distance) / self.track.length_m) + 1
            )
        car.pit_stops += 1
        remaining = (
            max(
                0.0, self.configuration.target_laps * self.track.length_m - car.distance
            )
            * per_m
        )
        strategy = car.configuration.strategy
        target = self.track.tank_capacity_kg
        if car.tire_change_pending:
            target = (
                self.track.tank_capacity_kg
                if car.target_tire == "wet"
                else car.fuel
            )
        if not car.tire_change_pending and strategy == "B" and car.pit_stops == 2:
            target = remaining
        if not car.tire_change_pending and strategy == "C":
            target = self.track.tank_capacity_kg * (0.5 if car.pit_stops == 1 else 1.0)
            if car.pit_stops == 3:
                target = remaining + per_m * self.track.length_m
        car.pit_added = max(0.0, min(self.track.tank_capacity_kg, target) - car.fuel)
        car.pit_remaining = max(
            car.configuration.pit_service_seconds,
            car.pit_added / self.track.refuel_kg_per_second,
        )
        car.pit_status, car.pit_requested = "in_pit", False
        self._emit(
            "pitstop",
            {
                "phase": "service_started",
                "stop_number": car.pit_stops,
                "fuel_added_kg": car.pit_added,
                "tire_compound": car.target_tire or car.active_tire,
                "lap": self._pit_lap(car),
                "pit_stop_time_ms": self._pit_elapsed_ms(car, service_at),
            },
            car,
            service_at,
        )

    def _pit_lap(self, car: PhysicalCar) -> int:
        """Retorne a volta em que a passagem atual pelos boxes começou."""
        return car.pit_lap_number or max(
            1, floor(max(0.0, car.distance) / self.track.length_m) + 1
        )

    @staticmethod
    def _pit_elapsed_ms(car: PhysicalCar, at: float) -> int:
        """Calcule o tempo cumulativo desde a entrada no pit lane."""
        start = car.pit_entry_time if car.pit_entry_time is not None else at
        return max(0, round((at - start) * 1000))

    def _crossings(
        self, car: PhysicalCar, previous: float, current: float, dt: float
    ) -> None:
        """Cronometre todas as passagens, inclusive múltiplas linhas no passo."""
        if current <= previous:
            return
        length = self.track.length_m
        for lap_index in range(
            max(0, floor(previous / length)), floor(current / length) + 1
        ):
            for fraction, checkpoint, sector in self.track.lines():
                boundary = (lap_index + fraction) * length
                if not previous < boundary <= current:
                    continue
                at = self.time + (boundary - previous) / (current - previous) * dt
                sector_ms = round((at - car.sector_start) * 1000) if sector else None
                self._emit(
                    "timing",
                    {
                        "driver_id": car.configuration.driver_id,
                        "team_id": car.configuration.team_id,
                        "lap": lap_index + 1,
                        "race_position": car.position,
                        "checkpoint_id": checkpoint,
                        "sector": sector,
                        "speed_kmh": car.speed * 3.6,
                        "lap_elapsed_ms": round((at - car.lap_start) * 1000),
                        "segment_time_ms": round((at - car.line_start) * 1000),
                        "sector_time_ms": sector_ms,
                        "pit_lap": car.pit_lap,
                        "valid": car.pit_status == "on_track",
                    },
                    car,
                    at,
                )
                car.line_start = at
                if sector:
                    car.sector_start = at
                    car.sector_times.append(sector_ms or 0)
                if checkpoint == "SF":
                    elapsed = round((at - car.lap_start) * 1000)
                    car.last_lap = elapsed
                    car.best_lap = min(car.best_lap or elapsed, elapsed)
                    car.worst_lap = max(car.worst_lap or elapsed, elapsed)
                    car.lap_start, car.pit_lap = at, car.pit_status != "on_track"
                    car.sector_times = []
                    if (
                        lap_index + 1 >= self.configuration.target_laps
                        or self.leader_finished is not None
                    ):
                        self.leader_finished = self.leader_finished or at
                        car.finished_at, car.status, car.speed = at, "finished", 0.0
                        car.distance = boundary
                        car.g_long = car.g_lat = car.throttle = car.brake = 0.0
                        car.g_valid = True
                        return

    def _rank(self) -> None:
        """Ordene chegada, distância percorrida e identificador estável."""
        ordered = sorted(
            self.cars,
            key=lambda c: (
                -c.distance,
                c.finished_at if c.finished_at is not None else float("inf"),
                c.configuration.car_id,
            ),
        )
        for index, car in enumerate(ordered, 1):
            car.position = index

    def snapshot(self) -> None:
        """Produza um quadro completo de telemetria com picos da janela."""
        self.snapshot_id += 1
        for car in self.cars:
            c = car.configuration
            progress = (car.distance / self.track.length_m) % 1
            completed = max(0, floor(car.distance / self.track.length_m))
            car.sequence += 1
            self._emit(
                "telemetry",
                {
                    "snapshot_id": self.snapshot_id,
                    "sample_sequence": car.sequence,
                    "driver_id": c.driver_id,
                    "driver_name": c.driver_name,
                    "driver_country_code": c.driver_country_code,
                    "team_id": c.team_id,
                    "speed_kmh": car.speed * 3.6,
                    "distance_m": car.distance,
                    "track_progress": progress,
                    "lap_distance_m": progress * self.track.length_m,
                    "race_position": car.position,
                    "lap": completed if car.status == "finished" else completed + 1,
                    "laps_completed": completed,
                    "sector": 1
                    + sum(progress >= v for v in self.track.sector_ends[:2]),
                    "target_laps": self.configuration.target_laps,
                    "race_status": self.status,
                    "car_status": car.status,
                    "fuel_kg": car.fuel,
                    "car_weight_kg": c.car_weight_kg + c.driver_weight_kg + car.fuel,
                    "gear": max(1, min(8, int(car.speed * 3.6 / 42) + 1)),
                    "rpm": 1000 + round(car.speed * 3.6 % 42 / 42 * 5000),
                    "throttle": car.throttle,
                    "brake": car.brake,
                    "tire_compound": car.active_tire,
                    "tire_age_laps": floor(car.tire_age),
                    "tire_pressure_psi": car.pressure,
                    "pit_status": car.pit_status,
                    "pit_stops": car.pit_stops,
                    "overtaking_lane": car.lane,
                    "driving_phase": "braking"
                    if car.brake > 0
                    else "corner"
                    if car.g_lat
                    else "straight",
                    "current_lap_time_ms": car.last_lap
                    if car.status == "finished" and car.last_lap is not None
                    else round(
                        (
                            (
                                car.retired_at
                                if car.retired_at is not None
                                else self.time
                            )
                            - car.lap_start
                        )
                        * 1000
                    ),
                    "last_lap_time_ms": car.last_lap,
                    "best_lap_time_ms": car.best_lap,
                    "worst_lap_time_ms": car.worst_lap,
                    "elapsed_race_seconds": self.time,
                    "g_longitudinal": car.g_long if car.g_valid else None,
                    "g_lateral": car.g_lat if car.g_valid else None,
                    "g_horizontal": hypot(car.g_long, car.g_lat)
                    if car.g_valid
                    else None,
                    "g_peak": car.peak_g,
                },
                car,
            )
            car.peak_g = 0.0

    def stop(self) -> None:
        """Encerre administrativamente sem criar aceleração ou volta artificial."""
        self.status = "stopped"
        for car in self.cars:
            car.speed = car.g_long = car.g_lat = car.throttle = car.brake = 0.0
            car.g_valid = True
        self._emit(
            "control",
            {
                "status": "stopped",
                "target_laps": self.configuration.target_laps,
                "participants": [],
                "track": asdict(self.track),
            },
        )
        self.snapshot()

    def drain_events(self) -> list[dict[str, Any]]:
        """Retorne os fatos pendentes e transfira sua posse ao publicador."""
        events, self.events = self.events, []
        return events

    def results(self) -> tuple[RaceResult, ...]:
        """Converta a classificação atual para o contrato persistido existente."""
        return tuple(
            RaceResult(
                self.configuration.race_id,
                c.configuration.car_id,
                c.position,
                max(0, floor(c.distance / self.track.length_m)),
                c.last_lap,
                c.best_lap,
                c.configuration.car_weight_kg,
                c.configuration.driver_weight_kg,
                c.configuration.top_speed_kmh,
                type(c.configuration.tire_compound)(c.active_tire),
            )
            for c in sorted(self.cars, key=lambda car: car.position)
        )
