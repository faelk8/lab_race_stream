"""Execução da corrida física com agenda de publicação independente."""

from typing import Any, Protocol

from racestream.application.ports import RaceControl, RaceRepository
from racestream.domain.physical import PhysicalRace
from racestream.domain.track import Track


class StreamPublisher(Protocol):
    """Porta de publicação dos fatos tipados da sessão."""

    def publish(self, event: dict[str, Any]) -> None:
        """Publique um fato preservando sua identidade."""

    def flush(self) -> None:
        """Confirme a entrega dos fatos pendentes ou propague a falha."""


class PhysicalWorker:
    """Execute uma prova manual com física fixa e snapshots a cada segundo."""

    def __init__(
        self,
        repository: RaceRepository,
        control: RaceControl,
        publisher: StreamPublisher,
        track: Track,
        time_scale: float = 45,
        seed: int = 42,
    ) -> None:
        """Inicialize dependências, escala física e semente da sessão."""
        if not 0 < time_scale <= 90:
            raise ValueError("A escala deve estar entre zero e 90")
        self.repository, self.control, self.publisher = repository, control, publisher
        self.track, self.time_scale, self.seed = track, time_scale, seed
        self.race: PhysicalRace | None = None
        self.active_race_id: str | None = None
        self.until_snapshot = 1.0

    def step(self, elapsed_seconds: float) -> None:
        """Consuma um comando, integre a física e publique fatos e quadros."""
        if self.race is None:
            configuration = self.control.claim_next_race()
            if configuration is None:
                return
            self.active_race_id = configuration.race_id
            self.race = PhysicalRace(
                configuration,
                self.repository.list_car_configurations(),
                self.track,
                self.seed,
                time_scale=self.time_scale,
            )
            self.until_snapshot = 1.0
            self.race.snapshot()
            self._publish()
            return
        status = self.control.get_race_status(self.race.configuration.race_id)
        if status == "paused":
            self.race.pause()
            self.race.snapshot()
            self._publish()
            return
        if status == "running" and self.race.paused:
            self.race.resume()
        if status in (
            "stopping",
            "stopped",
        ):
            self.stop_active()
            return
        remaining = elapsed_seconds
        while remaining > 1e-9 and self.race.status == "running":
            step = min(remaining, self.until_snapshot)
            self.race.advance(step * self.time_scale)
            remaining -= step
            self.until_snapshot -= step
            if self.until_snapshot <= 1e-9 or self.race.status == "finished":
                self.race.snapshot()
                self.until_snapshot = 1.0
            self._publish()
        if self.race.status == "finished":
            self.repository.finish_race(
                self.race.configuration.race_id, self.race.results()
            )
            self.race, self.active_race_id = None, None

    def _publish(self) -> None:
        """Publique e confirme, interrompendo a sessão em caso de falha."""
        assert self.race is not None
        events = self.race.drain_events()
        for event in events:
            self.publisher.publish(event)
        if events:
            self.publisher.flush()

    def stop_active(self) -> None:
        """Encerre a sessão atual, publique o estado e salve a classificação."""
        if self.race is not None:
            self.control.request_stop(self.race.configuration.race_id)
            self.race.stop()
            self._publish()
            self.repository.finish_race(
                self.race.configuration.race_id, self.race.results()
            )
            self.race, self.active_race_id = None, None

    def fail_active(self) -> None:
        """Registre sessão incompleta quando a execução/publicação falhar."""
        if self.active_race_id:
            self.control.fail_race(self.active_race_id)
        self.race, self.active_race_id = None, None
