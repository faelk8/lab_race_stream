"""Valide migrações repetidas e retenção em um schema PostgreSQL temporário."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from racestream.infrastructure.migrations import apply_migrations, load_migrations
from racestream.infrastructure.retention import expire_payloads


def main() -> None:
    """Exercite SQL real com rollback integral, sem dados de corridas do usuário."""
    schema = "teste_retencao_" + uuid4().hex
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        try:
            conn.execute(f'CREATE SCHEMA "{schema}"')
            conn.execute(f'SET search_path TO "{schema}"')
            with conn.cursor() as cursor:
                migrations = load_migrations(Path("postgres/initdb"))
                apply_migrations(cursor, migrations)
                apply_migrations(cursor, migrations)
            for race_id, status, days in (
                ("antiga", "finished", 60),
                ("ativa", "running", 60),
                ("pendente", "finished", 60),
                ("ultima", "finished", 0),
            ):
                conn.execute(
                    "INSERT INTO races (race_id,circuit_name,track_length_m,"
                    "duration_seconds,target_laps,status,started_at,finished_at) "
                    "VALUES (%s,'teste',4000,120,60,%s,"
                    "now()-make_interval(days=>%s),now()-make_interval(days=>%s))",
                    (race_id, status, days, days),
                )
                conn.execute(
                    "INSERT INTO stream_events (event_id,race_id,kind,car_id,"
                    "simulation_time_us,payload,received_at) VALUES (%s,%s,"
                    "'lap','CAR-01',1,'{\"lap\":1}',now()-interval '60 days')",
                    (race_id, race_id),
                )
            conn.execute(
                "INSERT INTO stream_outbox (event_id,payload) VALUES "
                "('pendente','{\"race_id\":\"pendente\"}')"
            )
            assert expire_payloads(conn) == 1
            assert conn.execute(
                "SELECT payload FROM stream_events WHERE event_id='antiga'"
            ).fetchone()["payload"] == {"lap": 1}
            assert expire_payloads(conn, apply=True) == 1
            assert expire_payloads(conn, apply=True) == 0
            assert (
                conn.execute("SELECT count(*) AS n FROM stream_events").fetchone()["n"]
                == 4
            )
            assert (
                conn.execute(
                    "SELECT payload FROM stream_events WHERE event_id='antiga'"
                ).fetchone()["payload"]
                == {}
            )
            # IDs expirados continuam únicos; replay não recria o histórico.
            assert (
                conn.execute(
                    "INSERT INTO stream_events SELECT * FROM stream_events "
                    "WHERE event_id='antiga' ON CONFLICT DO NOTHING "
                    "RETURNING event_id"
                ).fetchone()
                is None
            )
            print("Migrações repetidas e retenção segura aprovadas no PostgreSQL")
        finally:
            conn.rollback()


if __name__ == "__main__":
    main()
