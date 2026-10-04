"""Tests for deterministic race simulation behavior."""

from racestream.domain.models import (
    BASE_LAP_TIME_MS,
    CarConfiguration,
    TireCompound,
    calculate_lap_time_ms,
)
from racestream.domain.simulator import (
    CAR_MIN_SPACING_M,
    RACE_DURATION_SECONDS,
    TARGET_LAPS,
    TRACK_LENGTH_M,
    RaceSimulator,
    create_default_car_configurations,
)


def test_simulator_creates_twenty_independent_cars() -> None:
    """The default race must contain twenty uniquely identified cars."""
    simulator = RaceSimulator(seed=7)

    assert len(simulator.cars) == 20
    assert len({car.car_id for car in simulator.cars}) == 20
    assert len({car.driver_id for car in simulator.cars}) == 20


def test_tick_emits_one_event_per_car_and_reduces_fuel() -> None:
    """A simulation tick advances every car and accounts for fuel mass."""
    simulator = RaceSimulator(seed=12)
    initial_fuel = [car.fuel_kg for car in simulator.cars]

    events = simulator.tick()

    assert len(events) == 20
    assert all(
        car.fuel_kg < fuel
        for car, fuel in zip(simulator.cars, initial_fuel, strict=True)
    )
    assert all(
        car.car_weight_kg
        == car.configuration.car_weight_kg
        + car.configuration.driver_weight_kg
        + car.fuel_kg
        for car in simulator.cars
    )
    assert all(0.0 <= event.track_progress < 1.0 for event in events)
    assert {event.race_position for event in events} == set(range(1, 21))


def test_seed_reproduces_car_state() -> None:
    """Equal seeds produce equal simulation state across multiple ticks."""
    first = RaceSimulator(seed=31)
    second = RaceSimulator(seed=31)

    for _ in range(5):
        first.tick()
        second.tick()

    assert first.cars == second.cars


def test_progress_wraps_and_increments_lap() -> None:
    """Crossing the finish line increments lap and wraps track progress."""
    simulator = RaceSimulator(seed=4, car_count=1)
    car = simulator.cars[0]
    car.track_progress = 0.999
    car.speed_kmh = 340.0

    simulator.tick()

    assert car.lap == 2
    assert 0.0 <= car.track_progress < 1.0


def test_invalid_tick_duration_is_rejected() -> None:
    """Simulation time must move forward by a positive duration."""
    simulator = RaceSimulator(seed=2)

    try:
        simulator.tick(0)
    except ValueError as error:
        assert str(error) == "elapsed_seconds must be positive"
    else:
        raise AssertionError("tick accepted a non-positive duration")


def test_default_car_configurations_have_different_performance() -> None:
    """Default cars vary in mass, driver weight, top speed, and compound."""
    configurations = create_default_car_configurations()

    assert len(configurations) == 20
    assert len({configuration.car_weight_kg for configuration in configurations}) > 1
    assert len({configuration.driver_weight_kg for configuration in configurations}) > 1
    assert len({configuration.top_speed_kmh for configuration in configurations}) > 1
    assert len({configuration.tire_compound for configuration in configurations}) == 3


def test_tire_compound_and_vehicle_setup_change_lap_time_by_milliseconds() -> None:
    """Tire, vehicle, driver, and top-speed differences affect lap-time estimates."""
    baseline = CarConfiguration(
        car_id="CAR-01",
        driver_id="DRV-01",
        car_weight_kg=820.0,
        driver_weight_kg=75.0,
        top_speed_kmh=330.0,
        tire_compound=TireCompound.MEDIUM,
    )

    assert calculate_lap_time_ms(baseline) == BASE_LAP_TIME_MS
    assert (
        calculate_lap_time_ms(
            CarConfiguration(
                **{**baseline.__dict__, "tire_compound": TireCompound.SOFT}
            )
        )
        == BASE_LAP_TIME_MS - 250
    )
    assert calculate_lap_time_ms(baseline, tire_age_laps=2) == BASE_LAP_TIME_MS + 30


def test_baseline_race_represents_sixty_laps_in_two_minutes() -> None:
    """A massa do combustível, o desgaste e os boxes reduzem a distância da corrida."""
    baseline = CarConfiguration(
        car_id="CAR-01",
        driver_id="DRV-01",
        car_weight_kg=820.0,
        driver_weight_kg=75.0,
        top_speed_kmh=330.0,
        tire_compound=TireCompound.MEDIUM,
    )
    simulator = RaceSimulator(seed=9, car_configurations=(baseline,))

    event = simulator.tick(RACE_DURATION_SECONDS)[0]

    assert TARGET_LAPS - 1 <= event.lap <= TARGET_LAPS
    assert simulator.cars[0].pit_stops == 1
    assert simulator.cars[0].fuel_consumed_kg <= 220.0
    assert event.best_lap_time_ms == BASE_LAP_TIME_MS
    assert event.elapsed_race_seconds == RACE_DURATION_SECONDS
    assert event.race_status == "finished"


def test_car_brakes_and_downshifts_before_corner_entry() -> None:
    """Approaching a corner reduces speed, applies brake, and lowers gear."""
    configuration = create_default_car_configurations(1)[0]
    simulator = RaceSimulator(seed=14, car_configurations=(configuration,))
    car = simulator.cars[0]
    car.track_progress = 0.059
    car.speed_kmh = 300.0
    car.gear = 8

    simulator.tick(0.003)

    assert car.driving_phase == "braking"
    assert car.brake > 0.0
    assert car.speed_kmh < 300.0
    assert car.gear < 8


def test_car_reaccelerates_after_corner_and_caps_on_straight() -> None:
    """Cars accelerate after a corner and stop accelerating at top speed."""
    configuration = create_default_car_configurations(1)[0]
    simulator = RaceSimulator(seed=15, car_configurations=(configuration,))
    car = simulator.cars[0]
    car.track_progress = 0.11
    car.speed_kmh = 150.0

    simulator.tick(0.1)

    assert car.driving_phase == "straight"
    assert car.throttle > 0.0
    assert car.speed_kmh > 150.0

    car.track_progress = 0.11
    car.speed_kmh = configuration.top_speed_kmh - 0.1
    simulator.tick(0.001)

    assert car.speed_kmh < configuration.top_speed_kmh
    assert car.speed_kmh > configuration.top_speed_kmh * 0.95
    assert car.throttle == 0.0


def test_car_spacing_never_falls_below_minimum_gap() -> None:
    """The pack maintains a minimum physical separation during the race."""
    simulator = RaceSimulator(seed=22)
    for _ in range(80):
        simulator.tick(0.1)

    ordered_cars = sorted(
        [car for car in simulator.cars if car.overtaking_lane == 0],
        key=lambda car: (-(car.lap - 1 + car.track_progress), car.car_id),
    )
    gaps_m = [
        (
            (ahead.lap - 1 + ahead.track_progress)
            - (behind.lap - 1 + behind.track_progress)
        )
        * TRACK_LENGTH_M
        for ahead, behind in zip(ordered_cars, ordered_cars[1:], strict=False)
    ]

    assert all(gap >= CAR_MIN_SPACING_M - 0.001 for gap in gaps_m)
