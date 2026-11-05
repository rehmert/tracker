"""Release 414: scheduled replica context and manual-source compatibility."""

import sqlite3
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import backup, config
from scripts import tracker_replica


@pytest.fixture
def roots(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "tracker.db"

    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE sample(label TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO sample VALUES ('admin-only')"
        )

    primary = tmp_path / "primary"
    primary.mkdir()

    secondary = tmp_path / "secondary"
    secondary.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", database)
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{database}",
    )
    monkeypatch.setattr(backup, "BACKUP_DIR", primary)
    monkeypatch.setenv(
        "TRACKER_BACKUP_REPLICA_DIR",
        str(secondary),
    )

    return data, database, primary, secondary


def command(monkeypatch, *args):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tracker_replica.py", *args],
    )
    return tracker_replica.main()


def test_implicit_source_uses_validated_roots(
    roots, monkeypatch
):
    _, _, primary, secondary = roots
    calls = []

    def validate(*, destination):
        calls.append(("context", Path(destination)))
        return SimpleNamespace(
            primary=primary,
            secondary=secondary,
        )

    def replicate(source, target, keep):
        calls.append(("replicate", source, target, keep))
        return {
            "latest_archive": "tracker-test.zip",
            "latest_sha256": "test",
            "copied": 1,
            "matched": 0,
            "pruned": 0,
            "secondary": str(target),
        }

    monkeypatch.setattr(
        tracker_replica,
        "administrator_replication_context413",
        validate,
    )
    monkeypatch.setattr(
        tracker_replica,
        "replicate",
        replicate,
    )

    assert command(monkeypatch, "--keep", "4") == 0

    assert calls == [
        ("context", secondary),
        ("replicate", primary, secondary, 4),
    ]


def test_invalid_context_prevents_any_replication(
    roots, monkeypatch, capsys
):
    calls = []

    def invalid(*, destination):
        calls.append("context")
        raise ValueError("Invalid administrator storage")

    def unexpected(*args, **kwargs):
        calls.append("replicate")
        raise AssertionError("Replicate must not execute")

    monkeypatch.setattr(
        tracker_replica,
        "administrator_replication_context413",
        invalid,
    )
    monkeypatch.setattr(
        tracker_replica,
        "replicate",
        unexpected,
    )

    assert command(monkeypatch) == 1
    assert calls == ["context"]

    assert (
        "Invalid administrator storage"
        in capsys.readouterr().err
    )


def test_explicit_source_preserves_manual_behavior(
    roots, monkeypatch
):
    _, _, primary, secondary = roots
    manual = primary.parent / "manual"
    manual.mkdir()

    calls = []

    def unexpected(*args, **kwargs):
        raise AssertionError(
            "Manual source must not invoke admin preflight"
        )

    def replicate(source, target, keep):
        calls.append((source, target, keep))
        return {
            "latest_archive": "tracker-test.zip",
            "latest_sha256": "test",
            "copied": 0,
            "matched": 1,
            "pruned": 0,
            "secondary": str(target),
        }

    monkeypatch.setattr(
        tracker_replica,
        "administrator_replication_context413",
        unexpected,
    )
    monkeypatch.setattr(
        tracker_replica,
        "replicate",
        replicate,
    )

    assert command(
        monkeypatch,
        "--source", str(manual),
        "--dest", str(secondary),
        "--keep", "3",
    ) == 0

    assert calls == [(manual, secondary, 3)]


def test_read_only_context_check_without_source(
    roots, monkeypatch, capsys
):
    _, _, primary, secondary = roots

    def unexpected(*args, **kwargs):
        raise AssertionError(
            "Context check must not replicate"
        )

    monkeypatch.setattr(
        tracker_replica,
        "replicate",
        unexpected,
    )

    assert command(
        monkeypatch,
        "--context-check",
    ) == 0

    assert (
        "PASS: Administrator replication context valid"
        in capsys.readouterr().out
    )

    assert list(primary.iterdir()) == []
    assert list(secondary.iterdir()) == []


def test_real_default_replication_uses_admin_archive(
    roots, monkeypatch
):
    data, database, primary, secondary = roots

    archive = backup.create_backup(
        data_dir=data,
        backup_dir=primary,
    )

    database_before = database.read_bytes()

    assert command(monkeypatch, "--keep", "2") == 0

    replica = secondary / archive.name
    assert replica.is_file()
    assert replica.read_bytes() == archive.read_bytes()

    assert (
        secondary / tracker_replica.RECEIPT
    ).is_file()

    assert database.read_bytes() == database_before


def test_invalid_destination_refuses_copy_and_prune(
    roots, monkeypatch, tmp_path, capsys
):
    data, _, primary, secondary = roots

    backup.create_backup(data, primary)

    existing = secondary / "tracker-20200101T000000000000Z.zip"
    existing.write_bytes(b"keep-existing-copy")

    alias = tmp_path / "alias"
    alias.symlink_to(
        secondary,
        target_is_directory=True,
    )

    assert command(
        monkeypatch,
        "--dest", str(alias),
    ) == 1

    assert existing.read_bytes() == b"keep-existing-copy"
    assert len(list(secondary.iterdir())) == 1
    assert (
        "Symlinked"
        in capsys.readouterr().err
    )


def test_invalid_database_url_refuses_replication(
    roots, monkeypatch, capsys
):
    _, _, primary, secondary = roots

    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{secondary / 'wrong.db'}",
    )

    assert command(monkeypatch) == 1

    assert (
        "does not match"
        in capsys.readouterr().err
    )
    assert list(primary.iterdir()) == []
    assert list(secondary.iterdir()) == []


def test_missing_primary_archives_preserves_replica(
    roots, monkeypatch, capsys
):
    _, _, _, secondary = roots

    old = secondary / "tracker-20200101T000000000000Z.zip"
    old.write_bytes(b"preserve-old-copy")

    assert command(monkeypatch) == 1

    assert old.read_bytes() == b"preserve-old-copy"
    assert len(list(secondary.iterdir())) == 1

    assert (
        "No primary Tracker archives"
        in capsys.readouterr().err
    )


def test_tampered_primary_blocks_retention(
    roots, monkeypatch
):
    data, _, primary, secondary = roots
    archive = backup.create_backup(data, primary)

    with zipfile.ZipFile(archive, "a") as contents:
        contents.writestr(
            "unexpected.txt",
            "tampered",
        )

    old = secondary / "tracker-20200101T000000000000Z.zip"
    old.write_bytes(b"preserve-old-copy")

    assert command(monkeypatch, "--keep", "1") == 1

    assert old.read_bytes() == b"preserve-old-copy"
    assert len(list(secondary.iterdir())) == 1


def test_secondary_accounts_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
