"""PostgreSQL adapter for operational car and race data."""

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
        """Insert default car profiles without replacing operator settings."""
        configurations = create_default_car_configurations()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO cars (
                        car_id, driver_id, car_weight_kg, driver_weight_kg,
                        top_speed_kmh, tire_compound
                    ) VALUES (%s, %s, %s, %s, %s, %s)
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
                       top_speed_kmh, tire_compound
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
                    updated_at = now()
                WHERE car_id = %s
                RETURNING car_id, driver_id, car_weight_kg, driver_weight_kg,
                          top_speed_kmh, tire_compound
                """,
                (
                    configuration.driver_id,
                    configuration.car_weight_kg,
                    configuration.driver_weight_kg,
                    configuration.top_speed_kmh,
                    configuration.tire_compound.value,
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
                SET status = 'finished', finished_at = now()
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
    ) -> tuple[str, str, float, float, float, str]:
        """Return configuration fields in SQL parameter order."""
        return (
            configuration.car_id,
            configuration.driver_id,
            configuration.car_weight_kg,
            configuration.driver_weight_kg,
            configuration.top_speed_kmh,
            configuration.tire_compound.value,
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