"""Verifique transações e replay em um schema PostgreSQL temporário isolado.

Execute pelo Compose: docker compose exec -T api python < este_arquivo.py.
"""

import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from racestream.domain.models import RaceConfiguration
from racestream.domain.physical import PhysicalRace
from racestream.domain.simulator import create_default_car_configurations
from racestream.infrastructure.projection_store import ProjectionStore
from racestream.infrastructure.track_config import load_track


def main() -> None:
    """Teste duplicatas, reabertura, outbox e DLQ sem tocar nas corridas do usuário."""
    schema = "validacao_" + uuid4().hex
    store = ProjectionStore(os.environ["DATABASE_URL"])
    try:
        store.connection.execute(f'CREATE SCHEMA "{schema}"')
        store.connection.execute(f'SET search_path TO "{schema}"')
        store.connection.execute("CREATE TABLE races (race_id text PRIMARY KEY)")
        store.connection.execute(
            Path("postgres/initdb/005_stream_projections.sql").read_text()
        )
        race = PhysicalRace(
            RaceConfiguration("integracao"),
            create_default_car_configurations()[:2],
            load_track(),
        )
        race.snapshot()
        events = race.drain_events()
        race.advance(20)
        events.extend(race.drain_events())
        store.process_batch(
            [(event, "fixture", 0, offset, None) for offset, event in enumerate(events)]
        )
        before = store.snapshot("integracao")
        pending = store.pending()
        assert before and len(before["state"]["cars"]) == 2
        assert pending
        # Mesmos offsets e fatos em novos offsets não duplicam a projeção.
        for offset, event in enumerate(events):
            store.process(event, "fixture", 0, offset)
            store.process(event, "fixture", 1, offset)
        assert store.snapshot("integracao") == before
        assert store.pending() == pending
        timing = next(e for e in events if e["kind"] == "timing")
        history = store.history("integracao", timing["car_id"], "timing")
        semantic_duplicate = {**timing, "event_id": "reenvio-com-outra-identidade"}
        store.process(semantic_duplicate, "fixture", 3, 0)
        assert store.history("integracao", timing["car_id"], "timing") == history
        store.close()
        store = ProjectionStore(os.environ["DATABASE_URL"])
        store.connection.execute(f'SET search_path TO "{schema}"')
        assert store.snapshot("integracao") == before
        assert store.pending() == pending
        store.delivered([row["id"] for row in pending])
        assert store.pending() == []
        invalid = deepcopy(events[2])
        invalid["race_position"] = 0
        store.process(invalid, "fixture", 2, 0)
        assert store.snapshot("integracao") == before
        assert store.pending()[0]["payload"]["kind"] == "dead_letter"
        # Uma exceção durante a projeção também desfaz as mutações do evento.
        broken = deepcopy(events[0])
        broken["event_id"] = "controle-malformado"
        del broken["participants"]
        store.process_batch([(broken, "fixture", 2, 1, None)])
        assert store.snapshot("integracao") == before
        assert len(store.pending()) == 2
        print(
            "Validação PostgreSQL: replay, reabertura, outbox e rollback/DLQ aprovados."
        )
    finally:
        store.connection.execute("SET search_path TO public")
        store.connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        store.close()


if __name__ == "__main__":
    main()
