"""Persistência transacional de projeções, deduplicação e outbox."""

import json
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from racestream.application.event_contracts import validate_event
from racestream.application.projection import (
    apply_event,
    emit_frame,
    initial_projection,
)


class ProjectionStore:
    """Mantenha estado recuperável sem armazenar toda telemetria bruta."""

    def __init__(self, url: str) -> None:
        """Abra conexão reutilizável com transações explícitas."""
        self.connection = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        self._batch_states: dict[str, dict[str, Any]] | None = None
        self._batch_analytics: dict[str, dict[str, Any]] | None = None

    def process_batch(
        self, records: list[tuple[dict[str, Any] | None, str, int, int, str | None]]
    ) -> None:
        """Processe um lote atômico gravando cada projeção somente ao final."""
        self._batch_states, self._batch_analytics = {}, {}
        try:
            with self.connection.transaction():
                for record in records:
                    self.process(*record)
                for race, state in self._batch_states.items():
                    self._save_projection(race, state)
                analyses = list(self._batch_analytics.values())
                self._batch_analytics = None
                for analysis in analyses:
                    self._save_output(analysis)
        finally:
            self._batch_states = self._batch_analytics = None

    def process(
        self,
        event: dict[str, Any] | None,
        topic: str,
        partition: int,
        offset: int,
        error: str | None = None,
    ) -> None:
        """Confirme fato, projeção e outbox atomicamente, antes do offset Kafka."""
        with self.connection.transaction():
            receipt = self.connection.execute(
                "INSERT INTO stream_receipts VALUES (%s,%s,%s) ON CONFLICT DO "
                "NOTHING RETURNING offset_id",
                (topic, partition, offset),
            ).fetchone()
            if receipt is None:
                return
            try:
                if event is None or error:
                    raise ValueError(error or "Evento vazio")
                validate_event(event)
                with self.connection.transaction():
                    self._apply(event)
            except (ValueError, KeyError, TypeError) as exc:
                now = datetime.now(UTC).isoformat()
                failure = {
                    "kind": "dead_letter",
                    "event_id": f"erro:{topic}:{partition}:{offset}",
                    "race_id": event.get("race_id", "desconhecida")
                    if event
                    else "desconhecida",
                    "car_id": "",
                    "event_time": now,
                    "produced_at": now,
                    "simulation_time_us": 0,
                    "source_sequence": 0,
                    "track_version": "desconhecida",
                    "rules_version": "desconhecida",
                    "schema_version": 1,
                    "source_topic": topic,
                    "source_partition": partition,
                    "source_offset": offset,
                    "reason": str(exc)[:2000],
                }
                self._enqueue(failure)

    def _apply(self, event: dict[str, Any]) -> None:
        """Atualize a sessão bloqueada e preserve históricos de fatos discretos."""
        race = event["race_id"]
        if self._batch_states is not None and race in self._batch_states:
            state = json.loads(json.dumps(self._batch_states[race]))
        else:
            self.connection.execute(
                "INSERT INTO stream_sessions (race_id,projection) VALUES (%s,%s) "
                "ON CONFLICT DO NOTHING",
                (race, Jsonb(initial_projection())),
            )
            row = self.connection.execute(
                "SELECT projection FROM stream_sessions WHERE race_id=%s FOR UPDATE",
                (race,),
            ).fetchone()
            assert row is not None
            state = row["projection"]
        logical = (
            f"{race}:{event['car_id']}:{event['lap']}:{event['checkpoint_id']}"
            if event["kind"] == "timing"
            else event["event_id"]
        )
        if event["kind"] != "telemetry":
            inserted = self.connection.execute(
                """INSERT INTO stream_events
                (event_id,race_id,kind,car_id,logical_key,simulation_time_us,payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING event_id""",
                (
                    event["event_id"],
                    race,
                    event["kind"],
                    event["car_id"],
                    logical,
                    event["simulation_time_us"],
                    Jsonb(event),
                ),
            ).fetchone()
            if inserted is None:
                return
        output = apply_event(state, event)
        # Controle pode chegar depois da telemetria em outra partição.
        if event["kind"] == "control" and state["participants"]:
            frames = [
                frame
                for frame in state["frames"].values()
                if set(frame) == {p["car_id"] for p in state["participants"]}
            ]
            if frames:
                frame = max(frames, key=lambda f: next(iter(f.values()))["snapshot_id"])
                output += emit_frame(state, next(iter(frame.values())), frame, True)
        for item in output:
            self._save_output(item)
        if self._batch_states is not None:
            self._batch_states[race] = state
        else:
            self._save_projection(race, state)

    def _save_projection(self, race: str, state: dict[str, Any]) -> None:
        """Grave o estado dentro da transação que confirmou os fatos."""
        self.connection.execute(
            "UPDATE stream_sessions SET projection=%s, updated_at=now() WHERE "
            "race_id=%s",
            (Jsonb(state), race),
        )

    def _enqueue(self, event: dict[str, Any]) -> None:
        """Agende uma publicação idempotente dentro da transação atual."""
        self.connection.execute(
            "INSERT INTO stream_outbox (event_id,payload) VALUES (%s,%s) ON "
            "CONFLICT DO NOTHING",
            (event["event_id"], Jsonb(event)),
        )

    def _save_output(self, event: dict[str, Any]) -> None:
        """Salve histórico e quadro recuperável junto da publicação pendente."""
        kind = event["kind"]
        if kind == "analytics" and self._batch_analytics is not None:
            self._batch_analytics[event["race_id"]] = event
            return
        if kind in ("state", "analytics"):
            column = "state" if kind == "state" else "analytics"
            self.connection.execute(
                f"UPDATE stream_sessions SET {column}=%s WHERE race_id=%s",
                (Jsonb(event), event["race_id"]),
            )
        elif kind == "lap":
            self.connection.execute(
                """INSERT INTO stream_events
                (event_id,race_id,kind,car_id,simulation_time_us,payload)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    event["event_id"],
                    event["race_id"],
                    kind,
                    event["car_id"],
                    event["simulation_time_us"],
                    Jsonb(event),
                ),
            )
        self._enqueue(event)

    def flush_incomplete(self) -> None:
        """Libere quadros parciais após três segundos sem todos os participantes."""
        with self.connection.transaction():
            rows = self.connection.execute(
                "SELECT race_id,projection FROM stream_sessions WHERE updated_at < "
                "now()-interval '3 seconds' AND projection->'frames' <> '{}'::jsonb "
                "FOR UPDATE"
            ).fetchall()
            for row in rows:
                state = row["projection"]
                if not state["frames"]:
                    continue
                frame = state["frames"][max(state["frames"], key=int)]
                for event in emit_frame(
                    state, next(iter(frame.values())), frame, False
                ):
                    self._save_output(event)
                self.connection.execute(
                    "UPDATE stream_sessions SET projection=%s,updated_at=now() WHERE "
                    "race_id=%s",
                    (Jsonb(state), row["race_id"]),
                )

    def pending(self, limit: int = 300) -> list[dict[str, Any]]:
        """Liste mensagens da outbox em ordem de criação."""
        return self.connection.execute(
            "SELECT id,payload FROM stream_outbox ORDER BY id LIMIT %s", (limit,)
        ).fetchall()

    def delivered(self, ids: list[int]) -> None:
        """Remova apenas as publicações confirmadas pelo Kafka."""
        self.connection.execute("DELETE FROM stream_outbox WHERE id = ANY(%s)", (ids,))

    def snapshot(self, race_id: str) -> dict[str, Any] | None:
        """Leia estado e análises em um único snapshot PostgreSQL."""
        return self.connection.execute(
            "SELECT state,analytics,projection->'participants' AS "
            "participants, projection->'control' AS control FROM "
            "stream_sessions WHERE race_id=%s",
            (race_id,),
        ).fetchone()

    def history(self, race_id: str, car_id: str, kind: str) -> list[dict[str, Any]]:
        """Leia fatos discretos ordenados pelo relógio físico da prova."""
        return [
            row["payload"]
            for row in self.connection.execute(
                "SELECT payload FROM stream_events WHERE race_id=%s AND car_id=%s "
                "AND kind=%s ORDER BY simulation_time_us",
                (race_id, car_id, kind),
            ).fetchall()
        ]

    def close(self) -> None:
        """Feche a conexão PostgreSQL."""
        self.connection.close()
