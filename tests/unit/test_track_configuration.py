"""Rejeição antecipada de configurações incompatíveis com a física."""

from dataclasses import replace
from typing import Any

import pytest

from racestream.infrastructure.track_config import load_track


@pytest.mark.parametrize(
    "field",
    [
        "length_m",
        "physics_step_seconds",
        "acceleration_m_s2",
        "braking_m_s2",
        "refuel_kg_per_second",
        "pit_path_ratio",
        "pit_speed_kmh",
        "lateral_limit_g",
        "finish_timeout_seconds",
        "tank_capacity_kg",
        "fuel_tanks_per_reference",
        "grid_spacing_m",
    ],
)
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "10"])
def test_invalid_physical_parameter_is_rejected(field: str, value: Any) -> None:
    """Parâmetros não finitos ou sem unidade numérica falham antes da largada."""
    with pytest.raises(ValueError, match=field):
        replace(load_track(), **{field: value})


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"fuel_reference_laps": 0}, "fuel_reference_laps"),
        ({"fuel_reference_laps": 1.5}, "fuel_reference_laps"),
        ({"max_overtakes": -1}, "max_overtakes"),
        ({"max_overtakes": True}, "max_overtakes"),
        ({"map_start_offset": 1}, "map_start_offset"),
        ({"pit_entry": float("nan")}, "pit_entry"),
        ({"pit_box": 0.01, "pit_exit": 0.99}, "ordem"),
        ({"pit_box": 0.86}, "ordem"),
        ({"sector_ends": [0.34, 1]}, "três setores"),
        ({"sector_ends": [0.76, 0.34, 1]}, "ordenadas"),
        ({"checkpoints": [0.2, 0.2]}, "únicas"),
        ({"checkpoints": [float("nan")]}, "normalizadas"),
        ({"checkpoints": [0.34]}, "coincidir"),
        ({"checkpoints": [1]}, "coincidir"),
        ({"corners": [[0.1, 0.2]]}, "início, fim e raio"),
        ({"corners": [[0.1, 0.2, 0]]}, "raio não nulo"),
        ({"corners": [[0.1, 0.3, 50], [0.2, 0.4, -50]]}, "sobreposição"),
        ({"corners": [[0.1, 0.2, float("inf")]]}, "finitos"),
        ({"tire_grip_factors": {"soft": 1.01}}, "três compostos"),
        ({"tire_grip_factors": {"soft": 0, "medium": 1, "hard": 0.99}}, "aderência"),
    ],
)
def test_invalid_geometry_and_rules_fail_early(
    changes: dict[str, Any], reason: str
) -> None:
    """Geometria ambígua e parâmetros de autonomia inválidos têm erro explícito."""
    with pytest.raises(ValueError, match=reason):
        replace(load_track(), **changes)


def test_valid_signed_curves_and_wrapped_pit_lane() -> None:
    """Curvas adjacentes aceitam sentidos opostos e boxes cruzam a chegada."""
    track = replace(
        load_track(), corners=[[0.1, 0.2, 50], [0.2, 0.3, -60]], max_overtakes=0
    )
    assert track.radius_at(0.15) == 50
    assert track.radius_at(0.25) == -60
    assert track.pit_exit < track.pit_entry < track.pit_box
    assert len({p for p, _, _ in track.lines()}) == len(track.lines())


def test_whole_numbers_from_control_schema_remain_compatible() -> None:
    """O contrato de controle legado representa números inteiros como double."""
    values: dict[str, Any] = {"fuel_reference_laps": 60.0, "max_overtakes": 12.0}
    track = replace(load_track(), **values)
    assert track.fuel_reference_laps == 60
    assert track.max_overtakes == 12
