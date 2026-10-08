"""Sondagens limitadas de PostgreSQL e Kafka para readiness."""

import logging
import os
import threading
from collections.abc import Callable

import psycopg
from confluent_kafka.admin import AdminClient

from racestream.infrastructure.operational_health import OperationalHealth


def check_dependencies() -> dict[str, bool]:
    """Teste conexões sem registrar detalhes sensíveis das exceções."""
    checks = {"postgres": False, "kafka": False}
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as conn:
            conn.execute("SET statement_timeout = '3s'")
            conn.execute("SELECT 1")
        checks["postgres"] = True
    except Exception:
        logging.getLogger(__name__).warning("PostgreSQL indisponível na sondagem")
    try:
        admin = AdminClient(
            {
                "bootstrap.servers": os.environ.get(
                    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
                )
            }
        )
        checks["kafka"] = bool(admin.list_topics(timeout=3).brokers)
    except Exception:
        logging.getLogger(__name__).warning("Kafka indisponível na sondagem")
    return checks


class DependencyProbe:
    """Atualize readiness em segundo plano sem bloquear o loop da API."""

    def __init__(
        self, health: OperationalHealth, hub_alive: Callable[[], bool]
    ) -> None:
        """Associe a saúde da API à thread de distribuição de eventos."""
        self.health = health
        self.hub_alive = hub_alive
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        """Inicie a sondagem periódica."""
        self.thread.start()

    def stop(self) -> None:
        """Sinalize o encerramento e aguarde sondagens com timeout limitado."""
        self.stop_event.set()
        self.thread.join(timeout=10)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            self.health.heartbeat(
                inicializado=True, hub=self.hub_alive(), **check_dependencies()
            )
            self.stop_event.wait(10)
