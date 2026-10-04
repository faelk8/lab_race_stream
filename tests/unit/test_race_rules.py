"""Testes de regressão das regras de corrida definidas em corrida.md."""

import json
from collections import Counter
from dataclasses import replace
from io import BytesIO
from pathlib import Path

from fastavro import schemaless_reader, schemaless_writer

from racestream.application.telemetry import telemetry_to_payload
from racestream.domain.models import RaceRules
from racestream.domain.simulator import RaceSimulator, create_default_car_configurations


def test_grid_matches_team_and_athlete_specification() -> None:
    """Dez equipes têm dois carros, limites por categoria e peso do piloto pelo IMC."""
    cars = create_default_car_configurations()
    assert Counter(car.team_category for car in cars) == {"A": 8, "B": 8, "C": 4}
    assert len({car.team_id for car in cars}) == 10
    assert len({car.driver_name for car in cars}) == 20
    assert all(len(car.driver_country_code) == 2 for car in cars)
    assert set(Counter(car.team_id for car in cars).values()) == {2}
    for car in cars:
        weight, low, high = {
            "A": (500, 290, 320),
            "B": (510, 280, 310),
            "C": (515, 260, 290),
        }[car.team_category]
        assert car.car_weight_kg == weight
        assert low <= car.top_speed_kmh <= high
        assert 1.60 <= car.driver_height_m <= 1.90
        assert abs(car.driver_weight_kg / car.driver_height_m**2 - 22) < 0.01
        assert car.car_length_m == 3
        assert 3 <= car.pit_service_seconds <= 6


def test_strategy_initial_fuel_and_pit_targets() -> None:
    """A larga com tanque cheio; B e C largam com meio tanque e param no limite
    previsto.
    """
    profiles = create_default_car_configurations(3)
    simulator = RaceSimulator(seed=7, car_configurations=profiles)
    assert [car.fuel_kg for car in simulator.cars] == [110, 55, 55]
    for car, fuel in zip(simulator.cars, (0, 11, 22), strict=True):
        car.fuel_kg = fuel
    simulator.tick(0.001)
    assert all(car.pit_status == "in_pit" for car in simulator.cars)
    assert [car.pending_fuel_kg for car in simulator.cars] == [110, 110, 55]
    assert all(car.pit_stops == 1 for car in simulator.cars)


def test_pit_service_uses_physical_seconds_and_replaces_first_tire_set() -> None:
    """Uma parada de três segundos dura 3/45 segundos no relógio comprimido."""
    simulator = RaceSimulator(seed=1, car_count=1)
    car = simulator.cars[0]
    car.fuel_kg = 0
    car.tire_age_laps = 12
    car.tire_pressure_psi = 39.5
    simulator.tick(0.001)
    initial_progress = car.track_progress
    simulator.tick(0.06)
    assert car.pit_status == "in_pit"
    assert car.track_progress == initial_progress
    simulator.tick(0.007)
    assert car.pit_status == "on_track"
    assert car.fuel_kg == 110
    assert car.tire_age_laps == 0
    assert car.tire_pressure_psi == 38


def test_fuel_consumption_is_two_tanks_per_race_distance() -> None:
    """O consumo acompanha o movimento efetivo, independentemente do intervalo do
    passo.
    """
    simulator = RaceSimulator(seed=1, car_count=1)
    simulator.tick(0.5)
    car = simulator.cars[0]
    assert abs(car.fuel_consumed_kg - car.distance_laps * 220 / 60) < 1e-8
    assert abs(car.fuel_kg + car.fuel_consumed_kg - 110) < 1e-8


def test_burst_pressure_retires_car_without_negative_fuel() -> None:
    """Atingir 40 psi imobiliza o carro e emite um estado válido de abandono."""
    simulator = RaceSimulator(seed=1, car_count=1)
    simulator.cars[0].tire_pressure_psi = 40
    simulator.tick(0.001)
    event = simulator.tick(0.001)[0]
    assert event.pit_status == "tire_burst"
    assert event.speed_kmh == 0
    assert event.fuel_kg >= 0
    telemetry_to_payload(event)


def test_legacy_strategy_c_reports_insufficient_fuel_after_two_stops() -> None:
    """A configuração antiga sem terceira parada mantém o abandono por combustível."""
    configuration = replace(create_default_car_configurations(1)[0], strategy="C")
    simulator = RaceSimulator(
        seed=1,
        car_configurations=(configuration,),
        rules=RaceRules(strategy_c_extra_stop=False),
    )
    car = simulator.cars[0]
    car.fuel_kg = 0
    car.pit_stops = 2
    car.distance_laps = 57
    simulator.tick(0.001)
    assert car.retired
    assert car.pit_status == "out_of_fuel"
    assert car.pit_stops == 2


def test_overtake_budget_and_corner_blocking() -> None:
    """O tráfego mantém a ordem nas curvas ou após esgotar o limite de
    ultrapassagens.
    """
    profiles = create_default_car_configurations(2)
    for rules in (RaceRules(max_overtakes=0), RaceRules()):
        simulator = RaceSimulator(seed=1, car_configurations=profiles, rules=rules)
        for car in simulator.cars:
            car.track_progress = 0.07
            car.speed_kmh = 155
        simulator.cars[0].track_progress += 3 / simulator.track_length_m
        previous = [car.lap - 1 + car.track_progress for car in simulator.cars]
        simulator.tick(0.01)
        assert simulator.overtakes == 0
        assert simulator.cars[0].race_position == 1
        assert all(
            car.lap - 1 + car.track_progress >= before
            for car, before in zip(simulator.cars, previous, strict=True)
        )


def test_straight_allows_only_a_pair_to_pass() -> None:
    """O carro mais rápido ocupa a segunda faixa e completa a ultrapassagem na reta."""
    simulator = RaceSimulator(seed=1, car_count=2)
    for car in simulator.cars:
        car.track_progress = 0.11
        car.speed_kmh = 280
    simulator.cars[0].track_progress += 3 / simulator.track_length_m
    simulator.cars[0].configuration = replace(
        simulator.cars[0].configuration, top_speed_kmh=260
    )
    simulator.cars[1].configuration = replace(
        simulator.cars[1].configuration, top_speed_kmh=320
    )
    for _ in range(160):
        simulator.tick(0.001)
    assert simulator.overtakes == 1
    assert simulator.cars[1].race_position == 1
    assert len(simulator._passing) <= 1


def test_v3_avro_reads_v1_and_v2_with_defaults() -> None:
    """A nova telemetria mantém a compatibilidade com a resolução real de schemas
    Avro.
    """
    newest = json.loads(Path("schemas/telemetry-v3.avsc").read_text())
    payload = telemetry_to_payload(RaceSimulator(seed=1, car_count=1).tick(0.001)[0])
    for version in (1, 2):
        old = json.loads(Path(f"schemas/telemetry-v{version}.avsc").read_text())
        record = {field["name"]: payload[field["name"]] for field in old["fields"]}
        record.update(schema_version=version, event_type=f"race.telemetry.v{version}")
        buffer = BytesIO()
        schemaless_writer(buffer, old, record)
        buffer.seek(0)
        decoded = schemaless_reader(buffer, old, newest)
        assert isinstance(decoded, dict)
        assert decoded["tire_pressure_psi"] == 38
        assert decoded["pit_stops"] == 0
        assert decoded["overtaking_lane"] == 0


def test_exhausted_overtake_budget_blocks_straight_pass() -> None:
    """O carro mais rápido segue atrás na reta após esgotar as doze ultrapassagens."""
    simulator = RaceSimulator(seed=1, car_count=2)
    simulator.overtakes = 12
    for car in simulator.cars:
        car.track_progress = 0.11
        car.speed_kmh = 280
    simulator.cars[0].track_progress += 3 / simulator.track_length_m
    simulator.cars[0].configuration = replace(
        simulator.cars[0].configuration, top_speed_kmh=260
    )
    simulator.cars[1].configuration = replace(
        simulator.cars[1].configuration, top_speed_kmh=320
    )
    simulator.tick(0.15)
    assert simulator.overtakes == 12
    assert simulator.cars[0].race_position == 1
    assert all(car.overtaking_lane == 0 for car in simulator.cars)


def test_strategy_c_third_stop_targets_remaining_distance_and_one_lap() -> None:
    """A terceira parada deixa combustível para terminar e percorrer mais uma volta."""
    configuration = replace(create_default_car_configurations(1)[0], strategy="C")
    simulator = RaceSimulator(seed=1, car_configurations=(configuration,))
    car = simulator.cars[0]
    car.distance_laps = 42
    car.fuel_kg = 22
    car.pit_stops = 2
    car.tire_age_laps = 10
    car.tire_pressure_psi = 38.5

    simulator.tick(0.001)

    expected_fuel = (60 - 42 + 1) * 220 / 60
    assert car.pit_stops == 3
    assert car.pit_status == "in_pit"
    assert abs(car.pending_fuel_kg - expected_fuel) < 1e-8
    assert car.pending_fuel_kg < 110
    assert abs((car.pending_fuel_kg - car.fuel_kg) - 47.6666666667) < 1e-8
    simulator.tick(3 / 45)
    assert car.pit_status == "on_track"
    assert abs(car.fuel_kg - expected_fuel) < 1e-8
    assert car.tire_age_laps == 10
    assert car.tire_pressure_psi == 38.5
    assert not car.retired


def test_strategy_c_second_stop_fills_tank_before_final_refuel() -> None:
    """A segunda parada enche o tanque para permitir o trecho até a terceira."""
    configuration = replace(create_default_car_configurations(1)[0], strategy="C")
    simulator = RaceSimulator(seed=1, car_configurations=(configuration,))
    car = simulator.cars[0]
    car.distance_laps = 18
    car.fuel_kg = 22
    car.pit_stops = 1
    simulator.tick(0.001)
    assert car.pit_stops == 2
    assert car.pending_fuel_kg == 110


def test_strategy_c_reserve_uses_configured_race_distance() -> None:
    """A reserva de uma volta usa o consumo da distância configurada da prova."""
    configuration = replace(create_default_car_configurations(1)[0], strategy="C")
    simulator = RaceSimulator(
        seed=1, target_laps=30, car_configurations=(configuration,)
    )
    car = simulator.cars[0]
    car.distance_laps = 21
    car.fuel_kg = 22
    car.pit_stops = 2
    simulator.tick(0.001)
    assert abs(car.pending_fuel_kg - (30 - 21 + 1) * 220 / 30) < 1e-8
