"""Geometria física aproximada e regras configuráveis da pista."""

from dataclasses import dataclass, field
from math import sqrt


@dataclass(frozen=True)
class Track:
    """Defina a pista em metros e progresso normalizado, sem pixels de tela."""

    track_id: str
    version: str
    length_m: float
    description: str
    map_start_offset: float
    sector_ends: list[float]
    checkpoints: list[float]
    corners: list[list[float]]
    pit_entry: float
    pit_box: float
    pit_exit: float
    pit_speed_kmh: float
    pit_path_ratio: float
    physics_step_seconds: float
    acceleration_m_s2: float
    braking_m_s2: float
    lateral_limit_g: float
    finish_timeout_seconds: float
    refuel_kg_per_second: float
    max_overtakes: int
    fuel_reference_laps: int
    tank_capacity_kg: float
    fuel_tanks_per_reference: float
    grid_spacing_m: float
    tire_grip_factors: dict[str, float] = field(
        default_factory=lambda: {"soft": 1.01, "medium": 1.0, "hard": 0.99}
    )

    def __post_init__(self) -> None:
        """Rejeite configurações que tornariam a física ou as linhas inválidas."""
        if (
            min(
                self.length_m,
                self.physics_step_seconds,
                self.acceleration_m_s2,
                self.braking_m_s2,
                self.refuel_kg_per_second,
                self.pit_path_ratio,
            )
            <= 0
        ):
            raise ValueError("Parâmetros físicos devem ser positivos")
        if len(self.sector_ends) != 3 or self.sector_ends[-1] != 1:
            raise ValueError("A pista precisa de três setores terminando na chegada")
        for points in (self.sector_ends, self.checkpoints):
            if points != sorted(set(points)) or not all(0 < p <= 1 for p in points):
                raise ValueError("Linhas devem ser únicas, ordenadas e normalizadas")

    def radius_at(self, progress: float) -> float | None:
        """Retorne o raio assinado da curva atual ou nenhum raio na reta."""
        return next(
            (r for start, end, r in self.corners if start <= progress % 1 < end), None
        )

    def speed_limit(
        self, progress: float, top_speed: float, grip_factor: float = 1.0
    ) -> float:
        """Antecipe a frenagem usando distância e aderência lateral."""
        limit = top_speed
        for start, end, radius in self.corners:
            corner_speed = sqrt(
                self.lateral_limit_g * grip_factor * 9.80665 * abs(radius)
            )
            distance = (
                0.0
                if start <= progress < end
                else ((start - progress) % 1 * self.length_m)
            )
            limit = min(limit, sqrt(corner_speed**2 + 2 * self.braking_m_s2 * distance))
        return limit

    def lines(self) -> list[tuple[float, str, int]]:
        """Liste checkpoints, finais de setor e chegada na ordem física."""
        result = [(p, f"P{i:02d}", 0) for i, p in enumerate(self.checkpoints, 1)]
        result += [(p, f"S{i}", i) for i, p in enumerate(self.sector_ends[:2], 1)]
        result.append((1.0, "SF", 3))
        return sorted(result)
