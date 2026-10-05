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
from racestream.domain.models import RaceConfiguration
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
