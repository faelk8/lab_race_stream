"""Teste backup e recuperação em dois projetos Compose descartáveis e sem portas."""

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "backup_local", ROOT / "scripts/backup_local.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def minio(command, mode):
    """Grave ou leia um objeto de teste usando as credenciais internas locais."""
    action = (
        "mc mb --ignore-existing local/fixture; "
        "printf 'dados-do-laboratorio' | mc pipe local/fixture/prova.bin"
        if mode == "write"
        else "mc cat local/fixture/prova.bin"
    )
    return backup.run(
        command
        + [
            "exec",
            "-T",
            "minio",
            "sh",
            "-ec",
            "export MC_CONFIG_DIR=/tmp/mc-config; "
            'mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" '
            '"$MINIO_ROOT_PASSWORD" >/dev/null; ' + action,
        ],
        stdout=subprocess.PIPE,
    ).stdout


def main():
    """Confirme dump, objetos e IDs do Registry após restaurar volumes novos."""
    suffix = uuid4().hex[:10]
    source_name, target_name = (
        f"race-restore-source-{suffix}",
        f"race-restore-target-{suffix}",
    )
    source, target = (
        backup.compose(source_name, True),
        backup.compose(target_name, True),
    )
    try:
        backup.run(
            source
            + [
                "up",
                "-d",
                "--build",
                "--wait",
                "postgres",
                "minio",
                "kafka",
                "schema-registry",
            ]
        )
        backup.sql(
            source,
            "CREATE TABLE prova_backup (valor text); "
            "INSERT INTO prova_backup VALUES ('recuperado');",
        )
        minio(source, "write")
        schema = json.dumps(
            {"schema": json.dumps({"type": "record", "name": "Prova", "fields": []})}
        )
        result = backup.run(
            source
            + [
                "exec",
                "-T",
                "schema-registry",
                "curl",
                "-fsS",
                "-H",
                "Content-Type: application/vnd.schemaregistry.v1+json",
                "--data",
                schema,
                "http://localhost:8081/subjects/prova-value/versions",
            ],
            stdout=subprocess.PIPE,
        )
        schema_id = json.loads(result.stdout)["id"]
        with tempfile.TemporaryDirectory(prefix="racestream-backup-") as directory:
            snapshot = Path(directory) / "snapshot"
            backup.backup(source, snapshot)
            backup.run(source + ["stop"])
            backup.restore(snapshot, target_name)
            assert backup.sql(target, "SELECT valor FROM prova_backup") == "recuperado"
            object_bytes = minio(target, "read")
            assert object_bytes == b"dados-do-laboratorio", repr(object_bytes)
            restored = backup.run(
                target
                + [
                    "exec",
                    "-T",
                    "schema-registry",
                    "curl",
                    "-fsS",
                    f"http://localhost:8081/schemas/ids/{schema_id}",
                ],
                stdout=subprocess.PIPE,
            )
            assert json.loads(json.loads(restored.stdout)["schema"])["name"] == "Prova"
        print("Backup/restauração aprovados: PostgreSQL, MinIO e IDs Avro")
    finally:
        for command in (source, target):
            backup.run(command + ["down", "--volumes", "--remove-orphans"])


if __name__ == "__main__":
    main()
