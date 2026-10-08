"""Carregue e aplique migrações SQL com versão e checksum persistidos."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Migration:
    """Identifique o conteúdo imutável de uma migração SQL."""

    version: str
    filename: str
    checksum: str
    sql: str


class MigrationDriftError(RuntimeError):
    """Sinalize uma migração já aplicada cujo arquivo foi alterado."""


def load_migrations(directory: Path) -> tuple[Migration, ...]:
    """Leia migrações numeradas e calcule seus checksums SHA-256.

    :param directory: Diretório versionado com arquivos SQL.
    :return: Migrações ordenadas numericamente.
    :raises ValueError: Se o prefixo de versão for inválido ou repetido.
    """
    migrations = []
    seen: set[str] = set()
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        version = path.name[:3]
        if version in seen:
            raise ValueError(f"Versão de migração duplicada: {version}")
        seen.add(version)
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(version, path.name, sha256(sql.encode("utf-8")).hexdigest(), sql)
        )
    return tuple(migrations)


def apply_migrations(cursor: Any, migrations: tuple[Migration, ...]) -> None:
    """Aplique migrações pendentes e recuse alteração retroativa do SQL.

    A conexão deve manter uma transação aberta e adquirir exclusão mútua antes
    desta chamada, para registrar os DDLs e a tabela de controle atomicamente.

    :param cursor: Cursor DB-API transacional.
    :param migrations: Migrações ordenadas retornadas por :func:`load_migrations`.
    :raises MigrationDriftError: Se o checksum de uma versão aplicada mudou.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    for migration in migrations:
        cursor.execute(
            "SELECT filename, checksum FROM schema_migrations WHERE version = %s",
            (migration.version,),
        )
        applied = cursor.fetchone()
        if applied is not None:
            filename, checksum = (
                (applied["filename"], applied["checksum"])
                if isinstance(applied, Mapping)
                else applied
            )
            if filename != migration.filename or checksum != migration.checksum:
                raise MigrationDriftError(
                    f"A migração {migration.version} já aplicada foi alterada; "
                    "crie uma nova versão em vez de editar o arquivo existente."
                )
            continue
        cursor.execute(migration.sql)
        cursor.execute(
            """
            INSERT INTO schema_migrations (version, filename, checksum)
            VALUES (%s, %s, %s)
            """,
            (migration.version, migration.filename, migration.checksum),
        )
