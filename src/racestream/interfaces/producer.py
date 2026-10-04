"""Execute corridas solicitadas pelo painel e publique telemetria Avro no Kafka."""

import logging
import os
import signal
import threading
import time

from racestream.application.physical_worker import PhysicalWorker
from racestream.infrastructure.event_stream import EventStream
from racestream.infrastructure.postgres_repository import PostgresRaceRepository
from racestream.infrastructure.track_config import load_track
from racestream.interfaces.logging_config import configure_logging


def main() -> None:
    """Aguarde comandos do painel e execute uma corrida de cada vez."""
    configure_logging()
    logger = logging.getLogger(__name__)
    repository = PostgresRaceRepository(
        os.environ.get(
            "DATABASE_URL",
            "postgresql://racestream:racestream@localhost:5432/racestream",
        )
    )
    repository.seed_default_cars()
    repository.recover_interrupted_races()
    interval = float(os.environ.get("SIMULATION_INTERVAL_SECONDS", "0.1"))
    if interval <= 0:
        raise ValueError("O intervalo da simulação precisa ser positivo")
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signal, _frame: shutdown.set())
    signal.signal(signal.SIGINT, lambda _signal, _frame: shutdown.set())
    publisher = EventStream()
    worker = PhysicalWorker(
        repository,
        repository,
        publisher,
        load_track(),
        time_scale=float(os.environ.get("RACE_TIME_SCALE", "45")),
        seed=int(os.environ.get("RACE_SEED", "42")),
    )
    logger.info("Simulador pronto; aguardando início pelo painel")
    previous_tick = time.monotonic()
    try:
        while not shutdown.is_set():
            tick_started = time.monotonic()
            previous_race_id = worker.active_race_id
            try:
                worker.step(max(0.001, tick_started - previous_tick))
            except Exception:
                logger.exception("Falha ao executar o comando de corrida")
                worker.fail_active()
            if previous_race_id != worker.active_race_id:
                logger.info(
                    "Estado do simulador atualizado",
                    extra={"race_id": worker.active_race_id or previous_race_id},
                )
            previous_tick = tick_started
            shutdown.wait(max(0.0, interval - (time.monotonic() - tick_started)))
    finally:
        try:
            worker.stop_active()
        finally:
            publisher.close()
    logger.info("Simulador encerrado")


if __name__ == "__main__":
    main()
