"""Crie snapshots locais consistentes e restaure somente em projetos isolados."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRITERS = (
    "api",
    "simulator",
    "consumer",
    "spark-archive",
    "schema-registry",
    "kafka",
    "minio",
)
VOLUME_PATHS = {"kafka": "/var/lib/kafka/data", "minio": "/data"}


def compose(project: str | None = None, isolated: bool = False) -> list[str]:
    """Monte o comando sem interpolar valores em um shell."""
    command = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")]
    if isolated:
        command += ["-f", str(ROOT / "docker-compose.recovery.yml")]
    if project:
        command += ["-p", project]
    return command


def run(command: list[str], **kwargs):
    """Execute uma operação e propague qualquer falha."""
    return subprocess.run(command, check=True, **kwargs)


def sql(command: list[str], query: str) -> str:
    """Consulte o banco sem expor a senha ou o ambiente."""
    return (
        run(
            command
            + [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-ec",
                'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1',
            ],
            input=query.encode(),
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .strip()
    )


def checksum(path: Path) -> str:
    """Calcule SHA-256 sem carregar o arquivo inteiro na memória."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify(directory: Path) -> dict:
    """Recuse snapshots incompletos ou com qualquer arquivo alterado."""
    manifest = json.loads((directory / "manifest.json").read_text())
    expected = {"postgres.dump", "kafka.tar.gz", "minio.tar.gz"}
    if manifest.get("version") != 1 or set(manifest.get("files", {})) != expected:
        raise ValueError("Manifesto inválido ou backup incompleto")
    for name, digest in manifest["files"].items():
        if checksum(directory / name) != digest:
            raise ValueError(f"Checksum inválido: {name}")
    return manifest


def prune_backups(root: Path, keep: int = 3, days: int = 7) -> list[Path]:
    """Remova snapshots verificados com mais de sete dias, mantendo três.

    :param root: Diretório dedicado aos snapshots locais.
    :param keep: Quantidade mínima das pastas de backup mais recentes.
    :param days: Prazo mínimo de retenção em dias.
    :return: Pastas verificadas que foram removidas.
    """
    candidates = []
    for directory in root.iterdir():
        if directory.is_dir() and (directory / "manifest.json").is_file():
            try:
                verify(directory)
            except (ValueError, OSError, json.JSONDecodeError):
                continue
            candidates.append(directory)
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    cutoff = datetime.now(UTC) - timedelta(days=days)
    removed = []
    for directory in candidates[keep:]:
        created = datetime.fromisoformat(
            json.loads((directory / "manifest.json").read_text())["created_at"]
        )
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created < cutoff:
            shutil.rmtree(directory)
            removed.append(directory)
    return removed


def backup(command: list[str], destination: Path, prune: bool = False) -> None:
    """Interrompa escritores ociosos, copie o estado e retome só os serviços ativos."""
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    completed = False
    running = (
        run(
            command + ["ps", "--services", "--status", "running"],
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .split()
    )
    if not {"postgres", "minio", "kafka"} <= set(running):
        raise ValueError("Inicie PostgreSQL, MinIO e Kafka antes do backup")
    resume = [service for service in WRITERS if service in running]
    stopped: list[str] = []
    try:
        # Feche a entrada de comandos antes de conferir corridas em andamento.
        if "api" in resume:
            stopped.append("api")
            run(command + ["stop", "api"])
        active = sql(
            command,
            "SELECT count(*) FROM races WHERE status IN "
            "('queued','running','paused','stopping');",
        )
        if active != "0":
            raise ValueError("Finalize a corrida antes do backup, inclusive se pausada")
        for service in resume:
            if service not in stopped:
                stopped.append(service)
                run(command + ["stop", "-t", "60", service])
        with (destination / "postgres.dump").open("wb") as target:
            run(
                command
                + [
                    "exec",
                    "-T",
                    "postgres",
                    "sh",
                    "-ec",
                    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner',
                ],
                stdout=target,
            )
        for service, path in VOLUME_PATHS.items():
            container = (
                run(command + ["ps", "-a", "-q", service], stdout=subprocess.PIPE)
                .stdout.decode()
                .strip()
            )
            if not container:
                raise ValueError(f"Contêiner ausente: {service}")
            with (destination / f"{service}.tar.gz").open("wb") as target:
                run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--volumes-from",
                        f"{container}:ro",
                        "alpine:3.22",
                        "tar",
                        "-czf",
                        "-",
                        "-C",
                        path,
                        ".",
                    ],
                    stdout=target,
                )
        manifest = {
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "files": {p.name: checksum(p) for p in destination.iterdir()},
        }
        (destination / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        verify(destination)
        completed = True
        if prune:
            for removed in prune_backups(destination.parent):
                print(f"Backup expirado removido: {removed}")
        print(f"Backup local verificado: {destination}")
    finally:
        if stopped:
            run(command + ["start", *reversed(stopped)])
        if not completed:
            shutil.rmtree(destination, ignore_errors=True)


def restore(directory: Path, project: str) -> None:
    """Restaure em volumes novos e sem portas públicas; nunca sobrescreva a origem."""
    verify(directory)
    if not project.startswith("race-restore-"):
        raise ValueError("Use um projeto novo com prefixo race-restore-")
    command = compose(project, isolated=True)
    volumes = run(
        [
            "docker",
            "volume",
            "ls",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={project}",
        ],
        stdout=subprocess.PIPE,
    ).stdout.strip()
    containers = run(
        command + ["ps", "-a", "-q"], stdout=subprocess.PIPE
    ).stdout.strip()
    if volumes or containers:
        raise ValueError("Projeto de restauração já existe; use outro nome")
    run(command + ["create", "postgres", "minio", "kafka"])
    for service, path in VOLUME_PATHS.items():
        container = (
            run(command + ["ps", "-a", "-q", service], stdout=subprocess.PIPE)
            .stdout.decode()
            .strip()
        )
        with (directory / f"{service}.tar.gz").open("rb") as source:
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-i",
                    "--volumes-from",
                    container,
                    "alpine:3.22",
                    "tar",
                    "-xzf",
                    "-",
                    "-C",
                    path,
                ],
                stdin=source,
            )
    run(
        command
        + ["up", "-d", "--wait", "postgres", "minio", "kafka", "schema-registry"]
    )
    with (directory / "postgres.dump").open("rb") as source:
        run(
            command
            + [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-ec",
                'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
                "--clean --if-exists --no-owner --exit-on-error",
            ],
            stdin=source,
        )
    print(
        "Restauração isolada concluída; confirme históricos e objetos "
        "antes de remover o teste."
    )


def main() -> None:
    """Ofereça criação, verificação e restauração pelo terminal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify", "restore"))
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--project")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="remova backups verificados com mais de 7 dias, mantendo 3",
    )
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args()
    if args.directory is None:
        if args.action != "create":
            parser.error("Informe o diretório do backup")
        args.directory = (
            ROOT / "backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        )
    os.umask(0o077)
    try:
        if args.action == "create":
            backup(
                compose(args.project, args.isolated),
                args.directory.resolve(),
                args.prune,
            )
        elif args.action == "verify":
            verify(args.directory)
            print("Checksums válidos")
        elif not args.project:
            parser.error("Restauração exige --project race-restore-NOME")
        else:
            restore(args.directory.resolve(), args.project)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Operação interrompida: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
