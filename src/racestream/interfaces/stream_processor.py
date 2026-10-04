"""Consumer de cronometragem, projeções e publicação da outbox."""

import logging
import os
import signal
import threading
import time
from typing import Any

from racestream.application.event_contracts import SOURCE_KINDS
from racestream.infrastructure.event_stream import EventReader, EventStream
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
    last_flush = time.monotonic()
    processed: dict[tuple[str, int], Any] = {}
    batch: list[tuple[Any, Any, Any]] = []
    last_batch = time.monotonic()
    try:
        while not shutdown.is_set():
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
        logger.exception(
            "Falha no processamento; offsets não confirmados serão reprocessados"
        )
        raise
    finally:
        reader.close()
        store.close()
        stream.close()


if __name__ == "__main__":
    main()
