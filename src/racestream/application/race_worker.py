"""Execução incremental de corridas solicitadas pelo painel."""

from racestream.application.ports import EventPublisher, RaceControl, RaceRepository
from racestream.application.race_service import RaceRunService
from racestream.domain.simulator import RaceSimulator


class RaceWorker:
    """Execute uma corrida por solicitação, aguardando novos comandos ao encerrar."""

    def __init__(
        self,
        repository: RaceRepository,
        control: RaceControl,
        publisher: EventPublisher,
        seed: int = 42,
    ) -> None:
        """Inicialize o worker com portas injetadas.

        :param repository: Persistência de configurações e resultados.
        :param control: Coordenação dos comandos de corrida.
        :param publisher: Publicação de telemetria.
        :param seed: Semente determinística da simulação.
        """
        self._repository = repository
        self._control = control
        self._publisher = publisher
        self._seed = seed
        self._race_id: str | None = None
        self._simulator: RaceSimulator | None = None
        self._service: RaceRunService | None = None

    @property
    def active_race_id(self) -> str | None:
        """Retorne o identificador da corrida em execução, se houver."""
        return self._race_id

    def step(self, elapsed_seconds: float) -> None:
        """Consuma um comando ou avance um passo da corrida ativa.

        :param elapsed_seconds: Tempo de relógio desde o passo anterior.
        :raises RuntimeError: Se o estado persistido for incompatível com a execução.
        """
        if self._simulator is None:
            configuration = self._control.claim_next_race()
            if configuration is None:
                return
            self._race_id = configuration.race_id
            self._simulator = RaceSimulator(
                seed=self._seed,
                race_id=configuration.race_id,
                track_length_m=configuration.track_length_m,
                race_duration_seconds=configuration.duration_seconds,
                target_laps=configuration.target_laps,
                car_configurations=self._repository.list_car_configurations(),
            )
            self._service = RaceRunService(
                self._simulator,
                self._publisher,
                self._repository,
            )
            self._service.publish_snapshot()
            return
        assert self._service is not None
        status = self._control.get_race_status(self._simulator.race_id)
        if status in ("stopping", "stopped"):
            self._simulator.stop()
            self._service.publish_snapshot()
            self._service.persist_results()
            self._clear_active()
            return
        if status != "running":
            raise RuntimeError(f"Estado inesperado da corrida: {status}")
        self._service.publish_tick(elapsed_seconds)
        if self._simulator.race_status == "finished":
            self._service.persist_results()
            self._clear_active()

    def stop_active(self) -> None:
        """Encerre a corrida ativa ao desligar o processo do simulador."""
        if self._simulator is not None:
            self._control.request_stop(self._simulator.race_id)
            self.step(0.001)

    def fail_active(self) -> None:
        """Registre a falha e libere o worker para outra solicitação."""
        if self._race_id is not None:
            self._control.fail_race(self._race_id)
        self._clear_active()

    def _clear_active(self) -> None:
        """Libere o estado local após finalizar a corrida."""
        self._simulator = None
        self._service = None
        self._race_id = None
