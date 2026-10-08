"""Bridge Kafka telemetry into asynchronous WebSocket subscriptions."""

import asyncio
import logging
import os
import threading
import time

from racestream.infrastructure.event_stream import EventReader

LOGGER = logging.getLogger(__name__)


class KafkaTelemetryHub:
    """Fan out decoded Kafka events to bounded asyncio queues."""

    def __init__(self) -> None:
        """Create an inactive telemetry bridge."""
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._last_check = 0.0
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def is_ready(self) -> bool:
        """Indique conexão validada e atribuição de partições do consumidor."""
        return (
            self._ready.is_set()
            and not self._stop.is_set()
            and time.monotonic() - self._last_check < 30
            and self._thread is not None
            and self._thread.is_alive()
        )

    def subscriber_count(self) -> int:
        """Retorne a quantidade de assinantes conectados ao hub."""
        return len(self._subscribers)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the single Kafka consumer thread.

        :param loop: Event loop that owns WebSocket subscriber queues.
        """
        self._loop = loop
        self._thread = threading.Thread(
            target=self._consume,
            name="race-telemetry-consumer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the Kafka thread and wait for its consumer to close."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        """Create a bounded queue for one active WebSocket connection.

        :return: Queue containing the latest state events.
        """
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        """Remove a WebSocket queue from telemetry fanout.

        :param queue: Queue returned by :meth:`subscribe`.
        """
        self._subscribers.discard(queue)

    def _consume(self) -> None:
        """Read Kafka on a dedicated thread and reconnect after failures."""
        group_id = (
            os.environ.get("KAFKA_DASHBOARD_GROUP", "racestream-dashboard") + "-derived"
        )
        while not self._stop.is_set():
            consumer: EventReader | None = None
            try:
                consumer = EventReader(("state", "analytics", "control"), group_id)
                last_check = 0.0
                while not self._stop.is_set():
                    received = consumer.poll(timeout=0.5)
                    if time.monotonic() - last_check >= 10:
                        if consumer.ready():
                            self._ready.set()
                        else:
                            self._ready.clear()
                        last_check = time.monotonic()
                        self._last_check = last_check
                    if received is not None and self._loop is not None:
                        message, event, error = received
                        if error:
                            raise ValueError(error)
                        if event:
                            self._loop.call_soon_threadsafe(self._broadcast, event)
                            consumer.commit(message)
            except Exception:
                self._ready.clear()
                LOGGER.exception("Falha ao consumir projeções; reconectando")
                self._stop.wait(2.0)
            finally:
                if consumer is not None:
                    consumer.close()

    def _broadcast(self, event: dict[str, object]) -> None:
        """Publish one decoded event, dropping stale queued snapshots.

        :param event: Decoded v2 telemetry payload.
        """
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
