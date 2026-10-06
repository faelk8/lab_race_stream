"""Verifique os nomes públicos e estáveis dos tópicos Kafka."""

from racestream.application.event_contracts import TOPICS


def test_catalogo_usa_apelidos_curtos_e_unicos() -> None:
    """Garanta aliases curtos, únicos e alinhados ao fluxo atual."""
    assert TOPICS == {
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
    assert len(set(TOPICS.values())) == len(TOPICS)
