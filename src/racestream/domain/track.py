"""Geometria física aproximada e regras configuráveis da pista."""

from dataclasses import dataclass, field
from math import isfinite, sqrt


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
        default_factory=lambda: {
            "soft": 1.01,
            "medium": 1.0,
            "hard": 0.99,
            "wet": 0.98,
        }
    )

    def __post_init__(self) -> None:
        """Rejeite configurações que tornariam a física ou as linhas inválidas."""
        for name in (
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
        ):
            value = getattr(self, name)
            if not self._finite(value) or value <= 0:
                raise ValueError(f"{name} deve ser um número finito e positivo")
        for name, minimum in (("fuel_reference_laps", 1), ("max_overtakes", 0)):
            value = getattr(self, name)
            if not self._finite(value) or value < minimum or value != int(value):
                raise ValueError(
                    f"{name} deve ser inteiro e maior ou igual a {minimum}"
                )
        for name in ("map_start_offset", "pit_entry", "pit_box", "pit_exit"):
            value = getattr(self, name)
            if not self._finite(value) or not 0 <= value < 1:
                raise ValueError(
                    f"{name} deve estar no intervalo de 0 a 1, sem incluir 1"
                )
        service_distance = (self.pit_box - self.pit_entry) % 1
        exit_distance = (self.pit_exit - self.pit_entry) % 1
        if not 0 < service_distance < exit_distance:
            raise ValueError("Boxes devem seguir a ordem entrada, serviço e saída")
        if len(self.sector_ends) != 3 or self.sector_ends[-1] != 1:
            raise ValueError("A pista precisa de três setores terminando na chegada")
        for points in (self.sector_ends, self.checkpoints):
            if not all(self._finite(p) and 0 < p <= 1 for p in points):
                raise ValueError("Linhas devem ser únicas, ordenadas e normalizadas")
            if points != sorted(set(points)):
                raise ValueError("Linhas devem ser únicas, ordenadas e normalizadas")
        if set(self.checkpoints) & set(self.sector_ends):
            raise ValueError("Checkpoint não pode coincidir com setor ou chegada")
        previous_end = 0.0
        for corner in self.corners:
            if len(corner) != 3 or not all(self._finite(v) for v in corner):
                raise ValueError("Cada curva precisa de início, fim e raio finitos")
            start, end, radius = corner
            if not previous_end <= start < end <= 1 or radius == 0:
                raise ValueError(
                    "Curvas devem ser ordenadas, sem sobreposição e com raio não nulo"
                )
            previous_end = end
        if set(self.tire_grip_factors) != {"soft", "medium", "hard", "wet"} or not all(
            self._finite(value) and value > 0
            for value in self.tire_grip_factors.values()
        ):
            raise ValueError(
                "Informe aderência finita e positiva para os quatro compostos"
            )

    @staticmethod
    def _finite(value: object) -> bool:
        """Reconheça números finitos, rejeitando textos e valores booleanos."""
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
        )

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
