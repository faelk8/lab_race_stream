"""Verifique orden, idempotência e integridade do controle de migrações."""

from pathlib import Path

import pytest

from racestream.infrastructure.migrations import (
    MigrationDriftError,
    apply_migrations,
    load_migrations,
)


class MemoryCursor:
    """Simule o subconjunto DB-API usado pelo executor de migrações."""

    def __init__(self) -> None:
        self.ledger: dict[str, tuple[str, str]] = {}
        self.executed_sql: list[str] = []
        self.result: tuple[str, str] | None = None

    def execute(self, query: str, parameters: tuple[str, ...] | None = None) -> None:
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT filename, checksum"):
            self.result = self.ledger.get(parameters[0]) if parameters else None
        elif normalized.startswith("INSERT INTO schema_migrations"):
            assert parameters is not None
            version, filename, checksum = parameters
            self.ledger[version] = (filename, checksum)
        elif not normalized.startswith("CREATE TABLE IF NOT EXISTS schema_migrations"):
            self.executed_sql.append(query)

    def fetchone(self) -> tuple[str, str] | None:
        return self.result


def test_migrations_are_sorted_and_recorded_once(tmp_path: Path) -> None:
    """Migrações numeradas são aplicadas uma vez e ficam no registro."""
    (tmp_path / "002_segunda.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "001_primeira.sql").write_text("SELECT 1;", encoding="utf-8")
    cursor = MemoryCursor()
    migrations = load_migrations(tmp_path)

    assert [migration.version for migration in migrations] == ["001", "002"]
    apply_migrations(cursor, migrations)
    apply_migrations(cursor, migrations)

    assert len(cursor.executed_sql) == 2
    assert len(cursor.ledger) == 2


def test_checksum_drift_requires_a_new_migration(tmp_path: Path) -> None:
    """Uma versão aplicada não pode ser alterada silenciosamente."""
    path = tmp_path / "001_primeira.sql"
    path.write_text("SELECT 1;", encoding="utf-8")
    cursor = MemoryCursor()
    apply_migrations(cursor, load_migrations(tmp_path))
    path.write_text("SELECT 2;", encoding="utf-8")

    with pytest.raises(MigrationDriftError, match="crie uma nova versão"):
        apply_migrations(cursor, load_migrations(tmp_path))


def test_migrations_reject_duplicate_versions(tmp_path: Path) -> None:
    """Dois arquivos não podem declarar o mesmo número de versão."""
    (tmp_path / "001_primeira.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "001_repetida.sql").write_text("SELECT 2;", encoding="utf-8")

    with pytest.raises(ValueError, match="Versão de migração duplicada"):
        load_migrations(tmp_path)


def test_migrations_accept_dictionary_rows_from_real_repository(tmp_path: Path):
    """O adapter PostgreSQL usa dict_row também após reiniciar os serviços."""

    class DictionaryCursor(MemoryCursor):
        def fetchone(self):
            result = super().fetchone()
            return (
                dict(zip(("filename", "checksum"), result, strict=True))
                if result
                else None
            )

    path = tmp_path / "001_primeira.sql"
    path.write_text("SELECT 1;")
    cursor = DictionaryCursor()
    migrations = load_migrations(tmp_path)
    apply_migrations(cursor, migrations)
    apply_migrations(cursor, migrations)
    assert len(cursor.executed_sql) == 1
    path.write_text("SELECT 2;")
    with pytest.raises(MigrationDriftError):
        apply_migrations(cursor, load_migrations(tmp_path))
