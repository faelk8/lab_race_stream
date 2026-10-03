"""Tests for deterministic race simulation behavior."""

from racestream.domain.simulator import RaceSimulator


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
    assert all(car.car_weight_kg == 798.0 + car.fuel_kg for car in simulator.cars)
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