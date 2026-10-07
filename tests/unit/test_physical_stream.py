"""Validação do relógio físico, cronometragem e contratos de projeção."""

import json
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastavro import schemaless_reader, schemaless_writer
from test_race_worker import ControlledRepository

from racestream.application.event_contracts import validate_event
from racestream.application.physical_worker import PhysicalWorker
from racestream.application.projection import apply_event, initial_projection
from racestream.domain.models import RaceConfiguration, RaceIncident
from racestream.domain.physical import PhysicalRace
from racestream.domain.simulator import create_default_car_configurations
from racestream.infrastructure.track_config import load_track


@pytest.fixture(scope="module")
def short_race() -> tuple[PhysicalRace, list[dict[str, Any]]]:
    """Execute uma única prova curta compartilhada pelos testes de contratos."""
    race = PhysicalRace(
        RaceConfiguration("contrato-fisico", target_laps=2),
        create_default_car_configurations()[:2],
        load_track(),
    )
    race.snapshot()
    events = race.drain_events()
    for _ in range(400):
        race.advance(1)
        race.snapshot()
        events.extend(race.drain_events())
        if race.status == "finished":
            break
    assert race.status == "finished"
    return race, events


def test_measured_laps_and_sector_sum(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Todos os setores somam a volta medida, dentro do arredondamento de 1 ms."""
    race, events = short_race
    assert all(c.status == "finished" and c.fuel > 0 for c in race.cars)
    projection = initial_projection()
    laps: list[dict[str, Any]] = []
    for event in events:
        validate_event(event)
        laps.extend(e for e in apply_event(projection, event) if e["kind"] == "lap")
    assert len(laps) == 4
    assert all(abs(sum(e["sectors_ms"]) - e["lap_time_ms"]) <= 1 for e in laps)
    assert all(50_000 < e["lap_time_ms"] < 200_000 for e in laps)
    assert all(e["current_lap"] == 2 for e in laps)
    assert all(e["race_position"] in (1, 2) for e in laps)
    assert [
        c.position for c in sorted(race.cars, key=lambda c: c.finished_at or 0)
    ] == [
        1,
        2,
    ]


def test_new_avro_contracts_roundtrip(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Fontes e derivados reais atravessam os schemas Avro sem perda de campos."""
    _, events = short_race
    state = initial_projection()
    schemas = {}
    kinds = set()
    for source in events:
        for event in [source, *apply_event(state, source)]:
            kind = event["kind"]
            if kind not in schemas:
                schemas[kind] = json.loads(
                    Path(f"schemas/{kind}-stream.avsc").read_text()
                )
            buffer = BytesIO()
            schemaless_writer(buffer, schemas[kind], event)
            buffer.seek(0)
            decoded = schemaless_reader(buffer, schemas[kind])
            assert decoded == event
            kinds.add(kind)
    assert {"telemetry", "timing", "control", "state", "analytics", "lap"} <= kinds


def test_late_sectors_revise_final_analytics(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Setores atrasados completam a última volta e aumentam a revisão analítica."""
    _, events = short_race
    state = initial_projection()
    late = []
    for event in events:
        if event["kind"] == "timing" and event["lap"] == 2:
            late.append(event)
        else:
            apply_event(state, event)
    revision = state["analysis_sequence"]
    outputs = []
    for event in reversed(late):
        outputs.extend(apply_event(state, event))
    assert len([e for e in outputs if e["kind"] == "lap"]) == 2
    assert state["analysis_sequence"] > revision
    assert all(c["lap_count"] == 2 for c in outputs[-1]["cars"])


def test_replayed_frames_do_not_regress_ranking(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Quadros antigos não alteram a classificação final já projetada."""
    _, events = short_race
    state = initial_projection()
    for event in events:
        apply_event(state, event)
    previous = deepcopy(state)
    for event in events:
        if event["kind"] == "telemetry":
            apply_event(state, event)
    assert state == previous


def test_distance_and_acceleration_follow_fixed_step() -> None:
    """A distância inicial deriva da velocidade, sem depender da escala de exibição."""
    profiles = create_default_car_configurations()[:1]
    track = load_track()
    a = PhysicalRace(RaceConfiguration("a"), profiles, track)
    b = PhysicalRace(RaceConfiguration("b"), profiles, track)
    a.advance(1)
    for _ in range(10):
        b.advance(0.1)
    assert a.cars[0].distance == pytest.approx(b.cars[0].distance)
    assert a.cars[0].distance == pytest.approx(track.acceleration_m_s2 / 2)
    assert a.cars[0].g_long == pytest.approx(track.acceleration_m_s2 / 9.80665)


def test_starting_grid_has_two_columns_and_ten_rows() -> None:
    """Posicione os vinte carros em dez linhas com duas faixas laterais."""
    track = load_track()
    race = PhysicalRace(
        RaceConfiguration("grid-duplo"), create_default_car_configurations(), track
    )

    rows: dict[float, list[int]] = {}
    for car in race.cars:
        rows.setdefault(car.distance, []).append(car.lane)

    assert len(rows) == 10
    assert sorted(rows, reverse=True) == [
        -row * track.grid_spacing_m for row in range(10)
    ]
    assert all(sorted(lanes) == [0, 1] for lanes in rows.values())


def test_third_stop_adds_only_remaining_plus_reserve() -> None:
    """A terceira parada de C desconta o combustível a bordo e reserva uma volta."""
    profile = replace(create_default_car_configurations()[0], strategy="C")
    track = load_track()
    race = PhysicalRace(RaceConfiguration("reserva"), (profile,), track)
    car = race.cars[0]
    car.distance = 55.94 * track.length_m
    car.fuel = 12
    car.pit_stops = 2
    per_m = (
        track.tank_capacity_kg
        * track.fuel_tanks_per_reference
        / (track.fuel_reference_laps * track.length_m)
    )
    race._service(car, per_m)
    assert car.pit_stops == 3
    assert car.pit_added == pytest.approx(
        (60 - 55.94 + 1) * track.length_m * per_m - 12
    )
    car.tire_age = 7.0
    while car.pit_status == "in_pit":
        race.advance(track.physics_step_seconds)
    assert car.pit_status == "pit_lane"
    assert car.tire_age == 7.0
    assert car.fuel == pytest.approx((60 - 55.94 + 1) * track.length_m * per_m)


def test_rain_stop_schedule_staggers_every_car_by_two_to_six_laps() -> None:
    """Agende todos os carros com espaçamento reproduzível na janela de chuva."""
    race = PhysicalRace(
        RaceConfiguration(
            "estrategia-chuva", target_laps=60, rain_enabled=True, rain_start_lap=1
        ),
        create_default_car_configurations(),
        load_track(),
        seed=71,
    )
    schedule = [car.wet_stop_lap for car in race.cars]
    ordered_stops = sorted(lap for lap in schedule if lap is not None)
    assert len(schedule) == 20
    assert len(ordered_stops) == 20
    assert all(lap is not None and 1 <= lap < 60 for lap in schedule)
    assert all(
        2 <= right - left <= 6
        for left, right in zip(ordered_stops, ordered_stops[1:], strict=False)
    )
    assert schedule == race._rain_stop_schedule(20, 71)
    with pytest.raises(ValueError, match="tarde demais"):
        PhysicalRace(
            RaceConfiguration(
                "chuva-tardia", target_laps=60, rain_enabled=True, rain_start_lap=22
            ),
            create_default_car_configurations(),
            load_track(),
        )


def test_rain_intensity_increases_lap_time_with_wet_tires() -> None:
    """Chuva mais intensa reduz ritmo mesmo com composto de chuva montado."""
    profile = replace(
        create_default_car_configurations()[0], tire_compound=type(
            create_default_car_configurations()[0].tire_compound
        ).WET
    )

    def first_lap_time(intensity: float) -> int:
        race = PhysicalRace(
            RaceConfiguration(
                f"chuva-{intensity}",
                target_laps=2,
                rain_enabled=True,
                rain_start_lap=1,
                rain_intensity=intensity,
            ),
            (profile,),
            load_track(),
        )
        for _ in range(120):
            race.advance(1)
            if race.cars[0].last_lap is not None:
                break
        assert race.cars[0].pit_stops == 0
        return race.cars[0].last_lap or 0

    assert first_lap_time(1.0) > first_lap_time(0.25)


def test_rain_tire_stop_changes_compound_and_refuels() -> None:
    """A parada escalonada monta pneus de chuva e aproveita para abastecer."""
    race = PhysicalRace(
        RaceConfiguration(
            "troca-pneu-chuva",
            target_laps=8,
            rain_enabled=True,
            rain_start_lap=1,
            rain_intensity=0.8,
        ),
        create_default_car_configurations()[:1],
        load_track(),
    )
    car = race.cars[0]
    stop_events: list[dict[str, Any]] = []
    wet_snapshot_seen = False
    for _ in range(180):
        race.advance(1)
        race.snapshot()
        events = race.drain_events()
        stop_events.extend(event for event in events if event["kind"] == "pitstop")
        for event in events:
            if event["kind"] == "telemetry" and event["tire_compound"] == "wet":
                validate_event(event)
                wet_snapshot_seen = True
        if car.active_tire == "wet":
            break
    assert car.active_tire == "wet"
    assert car.fuel > 100
    assert wet_snapshot_seen
    assert any(
        event.get("phase") == "service_finished"
        and event.get("tire_compound") == "wet"
        and event.get("fuel_added_kg", 0) > 0
        for event in stop_events
    )


class CapturePublisher:
    """Capture eventos publicados sem executar Kafka."""

    def __init__(self) -> None:
        """Inicialize a captura de eventos."""
        self.events: list[dict[str, Any]] = []

    def publish(self, event: dict[str, Any]) -> None:
        """Armazene um fato enviado pelo worker."""
        self.events.append(event)

    def flush(self) -> None:
        """Confirme imediatamente a captura em memória."""


def test_worker_publishes_each_second_and_stops() -> None:
    """O worker publica 1 Hz e a parada não altera a distância percorrida."""
    repository = ControlledRepository()
    publisher = CapturePublisher()
    worker = PhysicalWorker(
        repository, repository, publisher, load_track(), time_scale=2
    )
    repository.request_start(RaceConfiguration("cadencia"))
    worker.step(0)
    publisher.events.clear()
    for _ in range(9):
        worker.step(0.1)
    assert not [e for e in publisher.events if e["kind"] == "telemetry"]
    worker.step(0.1)
    telemetry = [e for e in publisher.events if e["kind"] == "telemetry"]
    assert len(telemetry) == 2
    assert telemetry[0]["simulation_time_us"] == 2_000_000
    assert worker.race is not None
    previous = [c.distance for c in worker.race.cars]
    repository.request_stop("cadencia")
    worker.step(0.1)
    stopped = [e for e in publisher.events if e["kind"] == "telemetry"][-2:]
    assert [e["distance_m"] for e in stopped] == previous
    assert all(e["speed_kmh"] == 0 and e["throttle"] == 0 for e in stopped)


def test_strategy_a_requests_pit_before_last_reachable_entry() -> None:
    """A solicita os boxes antes de perder a última entrada alcançável."""
    track = load_track()
    profile = replace(create_default_car_configurations()[0], strategy="A")
    race = PhysicalRace(RaceConfiguration("entrada-a"), (profile,), track)
    car = race.cars[0]
    car.distance = 29.85 * track.length_m
    car.fuel = 0.15 * track.tank_capacity_kg * 2 / 60
    race.advance(25)
    assert car.pit_stops == 1
    assert car.status == "racing"


def test_lapped_finisher_stays_behind_more_laps() -> None:
    """Cruzar antes depois da bandeirada não supera um carro com mais voltas."""
    race = PhysicalRace(
        RaceConfiguration("chegada"),
        create_default_car_configurations()[:2],
        load_track(),
    )
    first, lapped = race.cars
    first.distance, first.finished_at = 60 * race.track.length_m, 4700
    lapped.distance, lapped.finished_at = 59 * race.track.length_m, 4690
    first.status = lapped.status = "finished"
    race._rank()
    assert first.position == 1


def test_strategy_a_finishes_with_one_stop() -> None:
    """A calibração nominal permite uma parada sem esgotar o combustível."""
    profile = replace(create_default_car_configurations()[0], strategy="A")
    race = PhysicalRace(RaceConfiguration("autonomia-a"), (profile,), load_track())
    for _ in range(600):
        race.advance(10)
        race.drain_events()
        if race.status == "finished":
            break
    assert race.cars[0].status == "finished"
    assert race.cars[0].pit_stops == 1
    assert race.cars[0].fuel > 0


def test_missing_car_keeps_previous_order(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Um carro ausente não paralisa os demais nem duplica posições."""
    from racestream.application.projection import emit_frame

    _, events = short_race
    state = initial_projection()
    for event in events[:3]:
        apply_event(state, event)
    original = deepcopy(state["cars"])
    event = deepcopy(events[1])
    event["snapshot_id"] = 5
    event["race_position"] = 2
    event["speed_kmh"] = 50
    output = emit_frame(state, event, {event["car_id"]: event}, False)
    assert len(output[0]["cars"]) == 2
    assert [c["telemetry"]["race_position"] for c in output[0]["cars"]] == [1, 2]
    assert sum(c["stale"] for c in output[0]["cars"]) == 1
    assert (
        state["cars"][event["car_id"]]["race_position"]
        == original[event["car_id"]]["race_position"]
    )


def test_gap_reference_is_shared_and_monotonic(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """Todos os gaps usam a mesma referência e respeitam a ordem do quadro."""
    _, events = short_race
    state = initial_projection()
    checked = False
    for event in events:
        for output in apply_event(state, event):
            if output["kind"] != "analytics":
                continue
            values = [c["gap_to_leader_ms"] for c in output["cars"]]
            if values and all(value is not None for value in values):
                assert values == sorted(values)
                assert len({c["gap_reference"] for c in output["cars"]}) == 1
                checked = True
    assert checked


def test_finish_does_not_start_a_phantom_lap(
    short_race: tuple[PhysicalRace, list[dict[str, Any]]],
) -> None:
    """A chegada conserva a volta concluída e seu tempo enquanto o grid termina."""
    _, events = short_race
    finished = [
        e for e in events if e["kind"] == "telemetry" and e["car_status"] == "finished"
    ]
    assert finished
    for event in finished:
        assert event["lap"] == event["laps_completed"] == 2
        assert event["current_lap_time_ms"] == event["last_lap_time_ms"]


@pytest.mark.parametrize("reason", ["out_of_fuel", "tire_burst", "prazo_de_chegada"])
def test_retired_clock_and_controls_remain_frozen(reason: str) -> None:
    """Abandono não mantém acelerador/G ativos nem faz o tempo individual crescer."""
    race = PhysicalRace(
        RaceConfiguration("abandono"),
        create_default_car_configurations()[:2],
        load_track(),
    )
    car = race.cars[0]
    race.advance(1)
    race.drain_events()
    if reason == "out_of_fuel":
        car.fuel = 0
    elif reason == "tire_burst":
        car.pressure = 40
    else:
        race.leader_finished = race.time - race.track.finish_timeout_seconds
    race.advance(0.02)
    incidents = [
        e
        for e in race.drain_events()
        if e["kind"] == "incident" and e["car_id"] == car.configuration.car_id
    ]
    assert len(incidents) == 1 and incidents[0]["reason"] == reason
    assert car.status == "retired"
    race.snapshot()
    first = next(
        e
        for e in race.drain_events()
        if e["kind"] == "telemetry" and e["car_id"] == car.configuration.car_id
    )
    race.advance(1)
    race.snapshot()
    latest = next(
        e
        for e in race.drain_events()
        if e["kind"] == "telemetry" and e["car_id"] == car.configuration.car_id
    )
    assert first["current_lap_time_ms"] == latest["current_lap_time_ms"]
    assert first["distance_m"] == latest["distance_m"]
    assert latest["speed_kmh"] == latest["throttle"] == latest["brake"] == 0
    assert latest["g_longitudinal"] == latest["g_lateral"] == 0


def test_pit_lane_limit_service_and_position_loss() -> None:
    """Respeite 60 km/h nos boxes, serviço parado e perda real de posição."""
    track = load_track()
    profiles = create_default_car_configurations()[:2]
    race = PhysicalRace(
        RaceConfiguration("boxes-60"),
        (replace(profiles[0], strategy="B"), profiles[1]),
        track,
    )
    car, rival = race.cars
    car.distance = 0.82 * track.length_m
    car.speed, car.fuel, car.tire_age = 70.0, 10.0, 8.0
    rival.distance = car.distance - 30
    rival.speed, rival.fuel = 70.0, 100.0
    entered = False
    serviced = False
    service_start = 0.0
    service_duration = 0.0
    stopped_distance = 0.0
    fuel_before = 0.0
    pit_events: list[dict[str, Any]] = []
    approach_speeds: list[float] = []
    for _ in range(4000):
        before = car.pit_status
        race.advance(track.physics_step_seconds)
        pit_events.extend(
            event for event in race.drain_events() if event["kind"] == "pitstop"
        )
        if car.pit_status != "on_track" or before != "on_track":
            assert car.speed * 3.6 <= 60.0 + 1e-8
        if before == "on_track" and car.pit_status == "pit_lane":
            entered = True
        if before == "pit_lane" and car.pit_status == "pit_lane" and car.pit_requested:
            approach_speeds.append(car.speed * 3.6)
        if before == "pit_lane" and car.pit_status == "in_pit":
            service_start = race.time
            service_duration = car.pit_remaining
            stopped_distance, fuel_before = car.distance, car.fuel
            assert service_duration >= car.configuration.pit_service_seconds
            assert service_duration >= car.pit_added / track.refuel_kg_per_second
            assert len(approach_speeds) >= 3
            assert approach_speeds[-3] > approach_speeds[-2] > approach_speeds[-1]
            assert approach_speeds[-1] <= track.braking_m_s2 * (
                track.physics_step_seconds * 3.6 * 2
            )
        if before == "in_pit":
            assert car.distance == stopped_distance
            assert car.speed == car.throttle == car.g_long == car.g_lat == 0
            if car.pit_status == "in_pit":
                assert car.fuel == fuel_before
                assert car.tire_age >= 8
            else:
                serviced = True
                assert race.time - service_start >= service_duration - 1e-8
                assert car.fuel > fuel_before
                assert car.tire_age == 0
        if entered and car.pit_status == "on_track":
            assert serviced
            assert car.position == 2
            assert rival.distance > car.distance
            assert [event["phase"] for event in pit_events] == [
                "entry",
                "service_started",
                "service_finished",
                "exit",
            ]
            assert all(event["lap"] >= 1 for event in pit_events)
            assert all(event["pit_stop_time_ms"] >= 0 for event in pit_events)
            assert pit_events[0]["pit_stop_time_ms"] == 0
            assert pit_events[-1]["pit_stop_time_ms"] > pit_events[-2][
                "pit_stop_time_ms"
            ]
            schema = json.loads(Path("schemas/pitstop-stream.avsc").read_text())
            for event in pit_events:
                validate_event(event)
                buffer = BytesIO()
                schemaless_writer(buffer, schema, event)
                buffer.seek(0)
                assert schemaless_reader(buffer, schema) == event
            break
    else:
        pytest.fail("O carro não completou a passagem pelos boxes em 80 segundos")


def test_puncture_scenario_requests_emergency_tire_change() -> None:
    """Furo configurado gera incidente e agenda uma parada emergencial."""
    profile = create_default_car_configurations()[0]
    race = PhysicalRace(
        RaceConfiguration(
            "furo-planejado",
            target_laps=4,
            incidents=(RaceIncident("tire_puncture", 1, profile.car_id),),
        ),
        (profile,),
        load_track(),
    )
    car = race.cars[0]
    car.distance = race.track.length_m * 0.5

    race._apply_scenarios(car, car.distance, 0.5)

    assert car.pit_requested and car.tire_change_pending
    assert any(
        event["kind"] == "incident" and event["reason"] == "tire_puncture"
        for event in race.events
    )
    car.fuel = 90.0
    per_m = (
        race.track.tank_capacity_kg
        * race.track.fuel_tanks_per_reference
        / (race.track.fuel_reference_laps * race.track.length_m)
    )
    race._service(car, per_m)
    assert car.pit_added == 0.0
    race._advance_car(car, car.pit_remaining + 0.1)
    assert car.pit_status == "pit_lane"
    assert car.tire_age == 0.0 and car.pressure == 38.0
    assert not car.tire_change_pending


def test_collision_scenario_retires_both_configured_cars() -> None:
    """Colisão programada registra abandono de ambos os participantes."""
    profiles = create_default_car_configurations()[:2]
    incident = RaceIncident("collision", 1, profiles[0].car_id, profiles[1].car_id)
    race = PhysicalRace(
        RaceConfiguration("colisao-planejada", target_laps=4, incidents=(incident,)),
        profiles,
        load_track(),
    )
    car = race.cars[0]
    car.distance = race.track.length_m * 0.5

    race._apply_scenarios(car, car.distance, 0.5)

    assert all(item.status == "retired" for item in race.cars)
    assert [
        event["reason"] for event in race.events if event["kind"] == "incident"
    ] == [
        "collision",
        "collision",
    ]


def test_rain_reduces_speed_on_the_configured_lap() -> None:
    """Chuva ativa reduz o limite de velocidade frente à mesma pista seca."""
    profile = create_default_car_configurations()[0]
    dry = PhysicalRace(
        RaceConfiguration("pista-seca", target_laps=4), (profile,), load_track()
    )
    wet = PhysicalRace(
        RaceConfiguration(
            "pista-molhada",
            target_laps=4,
            rain_enabled=True,
            rain_start_lap=1,
            rain_intensity=1.0,
        ),
        (profile,),
        load_track(),
    )
    for race in (dry, wet):
        race.cars[0].distance = race.track.length_m * 0.05
        race.cars[0].speed = 44.0
        race._advance_car(race.cars[0], 0.01)

    assert wet.cars[0].speed < dry.cars[0].speed
