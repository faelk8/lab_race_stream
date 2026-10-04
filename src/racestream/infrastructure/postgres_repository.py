"""PostgreSQL adapter for operational car and race data."""

from pathlib import Path
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from racestream.domain.models import (
    CarConfiguration,
    RaceConfiguration,
    RaceResult,
    RaceSnapshot,
    TireCompound,
)
from racestream.domain.simulator import create_default_car_configurations


class PostgresRaceRepository:
    """Persist car setup, race lifecycle, and final classification."""

    def __init__(self, connection_string: str) -> None:
        """Create the repository using a PostgreSQL connection string.

        :param connection_string: Psycopg connection URI.
        """
        self._connection_string = connection_string

    def seed_default_cars(self) -> None:
        """Aplique as migrações e insira os perfis preservando as edições existentes."""
        configurations = create_default_car_configurations()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for migration in (
                    "002_corrida_rules.sql",
                    "003_driver_identity.sql",
                    "004_race_control.sql",
                ):
                    cursor.execute(Path("postgres/initdb", migration).read_text())
                cursor.executemany(
                    """
                    INSERT INTO cars (
                        car_id, driver_id, car_weight_kg, driver_weight_kg,
                        top_speed_kmh, tire_compound, team_id, team_category,
                        driver_height_m, strategy, pit_service_seconds, car_length_m,
                        driver_name, driver_country_code
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (car_id) DO NOTHING
                    """,
                    [self._configuration_values(item) for item in configurations],
                )

    def list_car_configurations(self) -> tuple[CarConfiguration, ...]:
        """Return all configured cars in stable car-ID order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT car_id, driver_id, car_weight_kg, driver_weight_kg,
                       top_speed_kmh, tire_compound, team_id, team_category,
                        driver_height_m, strategy, pit_service_seconds, car_length_m,
                        driver_name, driver_country_code
                FROM cars
                ORDER BY car_id
                """
            ).fetchall()
        return tuple(self._configuration_from_row(row) for row in rows)

    def save_car_configuration(
        self,
        configuration: CarConfiguration,
    ) -> CarConfiguration:
        """Persist and return one validated car configuration.

        :param configuration: Configuration to insert or update.
        :return: Persisted configuration.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE cars
                SET driver_id = %s,
                    car_weight_kg = %s,
                    driver_weight_kg = %s,
                    top_speed_kmh = %s,
                    tire_compound = %s,
                    team_id = %s, team_category = %s, driver_height_m = %s,
                    strategy = %s, pit_service_seconds = %s, car_length_m = %s,
                    driver_name = %s, driver_country_code = %s,
                    updated_at = now()
                WHERE car_id = %s
                RETURNING car_id, driver_id, car_weight_kg, driver_weight_kg,
                          top_speed_kmh, tire_compound, team_id, team_category,
                        driver_height_m, strategy, pit_service_seconds, car_length_m,
                        driver_name, driver_country_code
                """,
                (
                    configuration.driver_id,
                    configuration.car_weight_kg,
                    configuration.driver_weight_kg,
                    configuration.top_speed_kmh,
                    configuration.tire_compound.value,
                    configuration.team_id,
                    configuration.team_category,
                    configuration.driver_height_m,
                    configuration.strategy,
                    configuration.pit_service_seconds,
                    configuration.car_length_m,
                    configuration.driver_name,
                    configuration.driver_country_code,
                    configuration.car_id,
                ),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown car_id: {configuration.car_id}")
        return self._configuration_from_row(row)

    def start_race(self, configuration: RaceConfiguration) -> None:
        """Persist a race as running before telemetry publication.

        :param configuration: Race timing and circuit configuration.
        """
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO races (
                    race_id, circuit_name, track_length_m, duration_seconds,
                    target_laps, status
                ) VALUES (%s, %s, %s, %s, %s, 'running')
                """,
                (
                    configuration.race_id,
                    configuration.circuit_name,
                    configuration.track_length_m,
                    configuration.duration_seconds,
                    configuration.target_laps,
                ),
            )

    def finish_race(self, race_id: str, results: tuple[RaceResult, ...]) -> None:
        """Persist final results and mark the race finished atomically.

        :param race_id: Race identifier to complete.
        :param results: Final result snapshot for every car.
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO race_results (
                        race_id, car_id, race_position, laps_completed,
                        last_lap_time_ms, best_lap_time_ms, car_weight_kg,
                        driver_weight_kg, top_speed_kmh, tire_compound
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (race_id, car_id) DO UPDATE SET
                        race_position = EXCLUDED.race_position,
                        laps_completed = EXCLUDED.laps_completed,
                        last_lap_time_ms = EXCLUDED.last_lap_time_ms,
                        best_lap_time_ms = EXCLUDED.best_lap_time_ms,
                        car_weight_kg = EXCLUDED.car_weight_kg,
                        driver_weight_kg = EXCLUDED.driver_weight_kg,
                        top_speed_kmh = EXCLUDED.top_speed_kmh,
                        tire_compound = EXCLUDED.tire_compound
                    """,
                    [self._result_values(item) for item in results],
                )
            connection.execute(
                """
                UPDATE races
                SET status = CASE WHEN status IN ('stopping', 'stopped')
                    THEN 'stopped' ELSE 'finished' END, finished_at = now()
                WHERE race_id = %s
                """,
                (race_id,),
            )

    def get_latest_race(self) -> RaceSnapshot | None:
        """Return the most recently created race, if one exists."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT race_id, circuit_name, duration_seconds, target_laps,
                       status, started_at::text, finished_at::text
                FROM races
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return RaceSnapshot(
            race_id=row["race_id"],
            circuit_name=row["circuit_name"],
            duration_seconds=row["duration_seconds"],
            target_laps=row["target_laps"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def request_start(self, configuration: RaceConfiguration) -> RaceSnapshot:
        """Solicite uma corrida, retornando a existente em caso de repetição.

        :param configuration: Configuração da nova corrida.
        :return: Corrida persistida ou já ativa.
        """
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(724163)")
            row = connection.execute(
                """SELECT * FROM races WHERE controlled
                AND status IN ('queued', 'running', 'stopping') LIMIT 1"""
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """INSERT INTO races (
                    race_id, circuit_name, track_length_m, duration_seconds,
                    target_laps, status, controlled
                    ) VALUES (%s, %s, %s, %s, %s, 'queued', true) RETURNING *""",
                    (
                        configuration.race_id,
                        configuration.circuit_name,
                        configuration.track_length_m,
                        configuration.duration_seconds,
                        configuration.target_laps,
                    ),
                ).fetchone()
        assert row is not None
        return self._snapshot_from_row(row)

    def request_stop(self, race_id: str) -> RaceSnapshot:
        """Solicite parada ou cancele a corrida que ainda aguarda execução.

        :param race_id: Identificador da corrida.
        :return: Estado persistido após o comando.
        :raises KeyError: Se a corrida não existir.
        """
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE races SET
                status = CASE WHEN status = 'queued' THEN 'stopped'
                    WHEN status = 'running' THEN 'stopping' ELSE status END,
                finished_at = CASE WHEN status = 'queued' THEN now()
                    ELSE finished_at END
                WHERE race_id = %s RETURNING *""",
                (race_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Corrida desconhecida: {race_id}")
        return self._snapshot_from_row(row)

    def claim_next_race(self) -> RaceConfiguration | None:
        """Reserve uma corrida pendente em uma única transação.

        :return: Configuração reservada ou nenhum trabalho pendente.
        """
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE races SET status = 'running', started_at = now()
                WHERE race_id = (
                    SELECT race_id FROM races WHERE controlled AND status = 'queued'
                    ORDER BY started_at LIMIT 1 FOR UPDATE SKIP LOCKED
                ) RETURNING *"""
            ).fetchone()
        if row is None:
            return None
        return RaceConfiguration(
            race_id=str(row["race_id"]),
            circuit_name=str(row["circuit_name"]),
            duration_seconds=float(row["duration_seconds"]),
            target_laps=int(row["target_laps"]),
            track_length_m=float(row["track_length_m"]),
        )

    def get_race_status(self, race_id: str) -> str:
        """Consulte o estado atual de controle.

        :param race_id: Identificador da corrida.
        :return: Estado persistido.
        :raises KeyError: Se a corrida não existir.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM races WHERE race_id = %s",
                (race_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Corrida desconhecida: {race_id}")
        return str(row["status"])

    def fail_race(self, race_id: str) -> None:
        """Registre falha sem alterar uma corrida já encerrada.

        :param race_id: Identificador da corrida.
        """
        with self._connect() as connection:
            connection.execute(
                """UPDATE races SET status = 'failed', finished_at = now()
                WHERE race_id = %s AND status IN ('queued', 'running', 'stopping')""",
                (race_id,),
            )

    def recover_interrupted_races(self) -> None:
        """Encerre corridas interrompidas ao reiniciar o único runner do Compose."""
        with self._connect() as connection:
            connection.execute(
                """UPDATE races SET status = 'stopped', finished_at = now()
                WHERE controlled AND status IN ('running', 'stopping')"""
            )

    @staticmethod
    def _snapshot_from_row(row: dict[str, Any]) -> RaceSnapshot:
        """Converta o registro operacional em estado de corrida."""
        return RaceSnapshot(
            race_id=str(row["race_id"]),
            circuit_name=str(row["circuit_name"]),
            duration_seconds=float(row["duration_seconds"]),
            target_laps=int(row["target_laps"]),
            status=str(row["status"]),
            started_at=str(row["started_at"]),
            finished_at=str(row["finished_at"]) if row["finished_at"] else None,
        )

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        """Open a dict-row connection to PostgreSQL."""
        return cast(
            psycopg.Connection[dict[str, Any]],
            psycopg.connect(
                self._connection_string,
                row_factory=cast(Any, dict_row),
            ),
        )

    @staticmethod
    def _configuration_values(
        configuration: CarConfiguration,
    ) -> tuple[object, ...]:
        """Return configuration fields in SQL parameter order."""
        return (
            configuration.car_id,
            configuration.driver_id,
            configuration.car_weight_kg,
            configuration.driver_weight_kg,
            configuration.top_speed_kmh,
            configuration.tire_compound.value,
            configuration.team_id,
            configuration.team_category,
            configuration.driver_height_m,
            configuration.strategy,
            configuration.pit_service_seconds,
            configuration.car_length_m,
            configuration.driver_name,
            configuration.driver_country_code,
        )

    @staticmethod
    def _configuration_from_row(row: dict[str, Any]) -> CarConfiguration:
        """Map one SQL row into the domain car configuration."""
        return CarConfiguration(
            car_id=str(row["car_id"]),
            driver_id=str(row["driver_id"]),
            car_weight_kg=float(row["car_weight_kg"]),
            driver_weight_kg=float(row["driver_weight_kg"]),
            top_speed_kmh=float(row["top_speed_kmh"]),
            tire_compound=TireCompound(str(row["tire_compound"])),
            team_id=str(row["team_id"]),
            team_category=str(row["team_category"]),
            driver_height_m=float(row["driver_height_m"]),
            strategy=str(row["strategy"]),
            pit_service_seconds=float(row["pit_service_seconds"]),
            car_length_m=float(row["car_length_m"]),
            driver_name=str(row["driver_name"]),
            driver_country_code=str(row["driver_country_code"]),
        )

    @staticmethod
    def _result_values(result: RaceResult) -> tuple[object, ...]:
        """Return result fields in SQL parameter order."""
        return (
            result.race_id,
            result.car_id,
            result.race_position,
            result.laps_completed,
            result.last_lap_time_ms,
            result.best_lap_time_ms,
            result.car_weight_kg,
            result.driver_weight_kg,
            result.top_speed_kmh,
            result.tire_compound.value,
        )
