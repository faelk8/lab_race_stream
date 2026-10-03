"""Bridge Kafka telemetry into asynchronous WebSocket subscriptions."""

import asyncio
import logging
import os
import threading

from racestream.infrastructure.kafka import AvroKafkaConsumer

LOGGER = logging.getLogger(__name__)


class KafkaTelemetryHub:
    """Fan out decoded Kafka events to bounded asyncio queues."""

    def __init__(self) -> None:
        """Create an inactive telemetry bridge."""
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

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
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=2)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        """Remove a WebSocket queue from telemetry fanout.

        :param queue: Queue returned by :meth:`subscribe`.
        """
        self._subscribers.discard(queue)

    def _consume(self) -> None:
        """Read Kafka on a dedicated thread and reconnect after failures."""
        topic = os.environ.get("KAFKA_TOPIC", "race.telemetry.raw")
        group_id = os.environ.get("KAFKA_DASHBOARD_GROUP", "racestream-dashboard")
        while not self._stop.is_set():
            consumer: AvroKafkaConsumer | None = None
            try:
                consumer = AvroKafkaConsumer(topic=topic, group_id=group_id)
                while not self._stop.is_set():
                    event = consumer.poll(timeout=0.5)
                    if event is not None and self._loop is not None:
                        self._loop.call_soon_threadsafe(self._broadcast, event)
            except Exception:
                LOGGER.exception("Dashboard Kafka consumer failed; reconnecting")
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