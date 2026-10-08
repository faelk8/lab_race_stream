"""Rejeite backups incompletos e snapshots com corrupção antes da restauração."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("backup_local", "scripts/backup_local.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_backup_manifest_and_corruption(tmp_path: Path):
    files = {}
    for name in ("postgres.dump", "minio.tar.gz", "kafka.tar.gz"):
        path = tmp_path / name
        path.write_bytes(b"fixture")
        files[name] = backup.checksum(path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "files": files}))
    assert backup.verify(tmp_path)["version"] == 1
    (tmp_path / "kafka.tar.gz").write_bytes(b"alterado")
    with pytest.raises(ValueError, match="Checksum"):
        backup.verify(tmp_path)
    manifest.write_text(json.dumps({"version": 1, "files": {}}))
    with pytest.raises(ValueError, match="incompleto"):
        backup.verify(tmp_path)


def test_restore_refuses_original_project(monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "verify", lambda _: {})
    with pytest.raises(ValueError, match="prefixo"):
        backup.restore(tmp_path, "lab_race_stream")


def test_retention_refuses_unsafe_windows():
    from racestream.infrastructure.retention import expire_payloads

    with pytest.raises(ValueError):
        expire_payloads(None, days=7)
    with pytest.raises(ValueError):
        expire_payloads(None, limit=0)


def test_prune_removes_only_verified_old_snapshots_and_keeps_three(tmp_path):
    from datetime import UTC, datetime, timedelta

    old_dirs = []
    recent_dirs = []
    for index in range(5):
        directory = tmp_path / f"snapshot-{index}"
        directory.mkdir()
        data = directory / "postgres.dump"
        data.write_bytes(f"conteudo-{index}".encode())
        backup_manifest = {
            "version": 1,
            "created_at": (datetime.now(UTC) - timedelta(days=10)).isoformat()
            if index < 2
            else datetime.now(UTC).isoformat(),
            "files": {name: "0" * 64 for name in ("kafka.tar.gz", "minio.tar.gz")},
        }
        # Manifesto completo para os três artefatos esperados.
        for name in ("kafka.tar.gz", "minio.tar.gz"):
            (directory / name).write_bytes(name.encode())
            backup_manifest["files"][name] = backup.checksum(directory / name)
        backup_manifest["files"][data.name] = backup.checksum(data)
        (directory / "manifest.json").write_text(json.dumps(backup_manifest))
        (old_dirs if index < 2 else recent_dirs).append(directory)
    removed = backup.prune_backups(tmp_path)
    assert set(removed) == set(old_dirs)
    assert all(not directory.exists() for directory in old_dirs)
    assert all(directory.exists() for directory in recent_dirs)
