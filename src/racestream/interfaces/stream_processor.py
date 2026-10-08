"""Consumer de cronometragem, projeções e publicação da outbox."""

import logging
import os
import signal
import threading
import time
from typing import Any

from racestream.application.event_contracts import SOURCE_KINDS
from racestream.infrastructure.event_stream import EventReader, EventStream
from racestream.infrastructure.operational_health import OperationalHealth, serve_health
from racestream.infrastructure.postgres_repository import PostgresRaceRepository
from racestream.infrastructure.projection_store import ProjectionStore
from racestream.interfaces.logging_config import configure_logging


def main() -> None:
    """Processe fatos, confirme offsets e entregue a outbox de forma recuperável."""
    configure_logging()
    logger = logging.getLogger(__name__)
    url = os.environ["DATABASE_URL"]
    PostgresRaceRepository(url).seed_default_cars()
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda _s, _f: shutdown.set())
    signal.signal(signal.SIGINT, lambda _s, _f: shutdown.set())
    store = ProjectionStore(url)
    stream = EventStream()
    reader = EventReader(SOURCE_KINDS, "racestream-projections-v1")
    health = OperationalHealth(float(os.environ.get("HEALTH_TIMEOUT_SECONDS", "60")))
    health.increment("consumer_events_total", 0)
    health.increment("consumer_decode_errors_total", 0)
    health.increment("consumer_failures_total", 0)
    server = serve_health(health, int(os.environ.get("HEALTH_PORT", "9101")))
    last_check = 0.0
    last_flush = time.monotonic()
    processed: dict[tuple[str, int], Any] = {}
    batch: list[tuple[Any, Any, Any]] = []
    last_batch = time.monotonic()
    try:
        while not shutdown.is_set():
            if time.monotonic() - last_check >= 10:
                store.connection.execute("SELECT 1")
                health.heartbeat(inicializado=True, postgres=True, kafka=reader.ready())
                row = store.connection.execute(
                    "SELECT count(*) AS total FROM stream_outbox"
                ).fetchone()
                health.set("outbox_pending", row["total"] if row else 0)
                last_check = time.monotonic()
            health.heartbeat()
            received = reader.poll(0.02)
            if received:
                batch.append(received)
            if batch and (len(batch) >= 100 or time.monotonic() - last_batch >= 0.05):
                store.process_batch(
                    [
                        (
                            event,
                            message.topic(),
                            message.partition(),
                            message.offset(),
                            error,
                        )
                        for message, event, error in batch
                    ]
                )
                for message, _, _ in batch:
                    processed[(message.topic(), message.partition())] = message
                health.increment("consumer_events_total", len(batch))
                health.set("consumer_last_event_timestamp_seconds", time.time())
                health.increment(
                    "consumer_decode_errors_total", sum(bool(e) for _, _, e in batch)
                )
                batch.clear()
                last_batch = time.monotonic()
            if time.monotonic() - last_flush >= 0.25:
                if processed:
                    reader.commit_processed(list(processed.values()))
                    processed.clear()
                store.flush_incomplete()
                pending = store.pending()
                for row in pending:
                    stream.publish(row["payload"])
                if pending:
                    stream.flush()
                    store.delivered([row["id"] for row in pending])
                last_flush = time.monotonic()
    except Exception:
        health.increment("consumer_failures_total")
        health.stop()
        logger.exception(
            "Falha no processamento; offsets não confirmados serão reprocessados"
        )
        raise
    finally:
        health.stop()
        server.shutdown()
        server.server_close()
        reader.close()
        store.close()
        stream.close()


if __name__ == "__main__":
    main()
