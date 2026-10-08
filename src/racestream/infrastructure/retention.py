"""Retenção local que preserva recibos e chaves de deduplicação."""

import argparse
import json
import os
from typing import Any

import psycopg

CANDIDATES = """
 SELECT e.event_id FROM stream_events e JOIN races r USING (race_id)
 WHERE r.status IN ('finished', 'stopped', 'failed')
   AND r.finished_at < now() - make_interval(days => %s)
   AND e.received_at < now() - make_interval(days => %s)
   AND e.payload <> '{}'::jsonb
   AND r.race_id <> (SELECT race_id FROM races ORDER BY started_at DESC LIMIT 1)
   AND NOT EXISTS (SELECT 1 FROM stream_outbox o
                   WHERE o.payload->>'race_id' = r.race_id)
 ORDER BY e.received_at LIMIT %s
"""


def expire_payloads(
    connection: Any, days: int = 30, limit: int = 10000, apply: bool = False
) -> int:
    """Expire somente conteúdo histórico; mantenha identidades para impedir replay.

    :param connection: Conexão PostgreSQL com suporte a transações.
    :param days: Idade mínima; nunca menor que oito dias.
    :param limit: Quantidade máxima de linhas por execução.
    :param apply: Execute a alteração; falso somente conta candidatos.
    :return: Quantidade de candidatos ou conteúdos expirados.
    """
    if days < 8 or limit < 1 or limit > 100000:
        raise ValueError("Use ao menos oito dias e lote entre 1 e 100000")
    with connection.transaction():
        connection.execute("SET LOCAL statement_timeout = '30s'")
        if apply:
            # Não remova IDs nem logical_key: a deduplicação semântica é permanente.
            query = (
                "UPDATE stream_events SET payload='{}'::jsonb WHERE event_id IN ("
                + CANDIDATES
                + ") RETURNING event_id"
            )
            return len(connection.execute(query, (days, days, limit)).fetchall())
        return len(connection.execute(CANDIDATES, (days, days, limit)).fetchall())


def main() -> None:
    """Simule a expiração por padrão; alterações exigem opção explícita."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
        count = expire_payloads(connection, args.days, args.limit, args.apply)
    print(
        json.dumps(
            {"aplicado": args.apply, "conteudos": count, "dias": args.days},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
