"""Catálogo tipado dos eventos novos e validação de invariantes."""

from math import isfinite
from typing import Any

TOPICS = {
    "telemetry": "telemetry",
    "validated": "validated",
    "timing": "timing",
    "lap": "lap_completed",
    "pitstop": "pitstop",
    "incident": "incident",
    "control": "control",
    "state": "state",
    "analytics": "analytics",
    "dead_letter": "dead_letter",
}
SOURCE_KINDS = ("telemetry", "timing", "pitstop", "incident", "control")


def validate_event(event: dict[str, Any]) -> None:
    """Valide identidade, relógio e limites sem depender do transporte."""
    if not event.get("event_id") or not event.get("race_id"):
        raise ValueError("Evento sem identidade de corrida")
    if event.get("kind") not in SOURCE_KINDS:
        raise ValueError("Tipo de evento não aceito como fonte")
    if (
        not isfinite(event.get("simulation_time_us", -1))
        or event.get("simulation_time_us", -1) < 0
    ):
        raise ValueError("Tempo físico negativo")
    if event.get("kind") == "telemetry":
        if not 0 <= event["track_progress"] < 1 or event["race_position"] < 1:
            raise ValueError("Posição inválida")
        if not 0 <= event["speed_kmh"] <= 380 or not 0 <= event["fuel_kg"] <= 110.001:
            raise ValueError("Velocidade ou combustível inválido")
    if event.get("kind") == "timing":
        if event["lap_elapsed_ms"] < 0 or event["segment_time_ms"] < 0:
            raise ValueError("Parcial negativa")
        if event["sector"] not in (0, 1, 2, 3):
            raise ValueError("Setor inválido")
        if event["sector"] and (
            event["sector_time_ms"] is None or event["sector_time_ms"] < 0
        ):
            raise ValueError("Setor sem tempo válido")
