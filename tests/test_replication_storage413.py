"""Release 413: administrator replication preflight is read-only."""
from dataclasses import FrozenInstanceError
import sqlite3
import sys

import pytest

from app import backup, config
from app.replication_storage413 import (
    administrator_replication_context413,
)
from scripts import tracker_replica


@pytest.fixture
def roots(tmp_path, monkeypatch):
    data = tmp_path / "admin-data"
    data.mkdir()
    database = data / "tracker.db"

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE example (id INTEGER)"
        )

    primary = tmp_path / "primary"
    primary.mkdir()
    secondary = tmp_path / "replica"
    secondary.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", database)
    monkeypatch.setattr(
        config, "DB_URL", f"sqlite:///{database}"
    )
    monkeypatch.setattr(backup, "BACKUP_DIR", primary)
    monkeypatch.setenv(
        "TRACKER_BACKUP_REPLICA_DIR", str(secondary)
    )
    return data, database, primary, secondary


def test_valid_admin_context_is_immutable_and_read_only(roots):
    data, database, primary, secondary = roots
    before = (
        set(data.iterdir()),
        set(primary.iterdir()),
        set(secondary.iterdir()),
    )

    selected = administrator_replication_context413()

    assert selected.user_id == 1
    assert selected.scope == "legacy-admin-instance"
    assert selected.data_dir == data
    assert selected.database == database
    assert selected.primary == primary
    assert selected.secondary == secondary

    with pytest.raises(FrozenInstanceError):
        selected.secondary = primary

    assert before == (
        set(data.iterdir()),
        set(primary.iterdir()),
        set(secondary.iterdir()),
    )


@pytest.mark.parametrize(
    "user_id", [0, 2, 3, True, "1", None],
)
def test_secondary_and_invalid_identity_denied(roots, user_id):
    with pytest.raises(PermissionError):
        administrator_replication_context413(
            user_id=user_id
        )


def test_missing_primary_directory_rejected_before_writes(roots):
    _, _, primary, secondary = roots
    primary.rmdir()

    with pytest.raises(ValueError, match="backup directory"):
        administrator_replication_context413()

    assert list(secondary.iterdir()) == []


def test_missing_destination_rejected_before_writes(
    roots, tmp_path,
):
    _, _, primary, _ = roots

    with pytest.raises(
        ValueError, match="already be a directory"
    ):
        administrator_replication_context413(
            tmp_path / "missing"
        )

    assert list(primary.iterdir()) == []


def test_symlinked_destination_and_parent_rejected(
    roots, tmp_path,
):
    _, _, primary, secondary = roots
    alias = tmp_path / "alias"
    alias.symlink_to(
        secondary, target_is_directory=True
    )

    with pytest.raises(ValueError, match="Symlinked"):
        administrator_replication_context413(alias)

    nested = secondary / "inside"
    nested.mkdir()

    with pytest.raises(ValueError, match="Symlinked"):
        administrator_replication_context413(
            alias / "inside"
        )

    assert list(primary.iterdir()) == []


@pytest.mark.parametrize(
    "relative", ["backup", "../replica", ""],
)
def test_relative_and_empty_destination_rejected(
    roots, relative,
):
    with pytest.raises(ValueError, match="absolute path"):
        administrator_replication_context413(relative)


def test_equal_and_nested_replica_directories_rejected(roots):
    data, _, primary, _ = roots
    child = primary / "nested"
    child.mkdir()
    uploads = data / "uploads"
    uploads.mkdir()

    for selected in (
        primary, child, primary.parent, data, uploads,
    ):
        with pytest.raises(ValueError, match="overlap"):
            administrator_replication_context413(
                selected
            )


def test_mismatched_database_url_rejected(
    roots, monkeypatch,
):
    _, _, primary, secondary = roots

    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{secondary / 'wrong.db'}",
    )

    with pytest.raises(ValueError, match="does not match"):
        administrator_replication_context413()

    assert list(primary.iterdir()) == []


def test_context_check_cli_does_not_replicate(
    roots, monkeypatch, capsys,
):
    _, _, primary, secondary = roots

    monkeypatch.setattr(sys, "argv", [
        "tracker_replica.py",
        "--source", str(primary),
        "--dest", str(secondary),
        "--context-check",
    ])

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Replica must not run during preflight"
        )

    monkeypatch.setattr(
        tracker_replica, "replicate", forbidden
    )

    assert tracker_replica.main() == 0

    assert (
        "PASS: Administrator replication context valid"
        in capsys.readouterr().out
    )
    assert list(primary.iterdir()) == []
    assert list(secondary.iterdir()) == []


def test_context_check_rejects_unconfigured_source(
    roots, monkeypatch, tmp_path, capsys,
):
    _, _, primary, secondary = roots
    wrong = tmp_path / "wrong"
    wrong.mkdir()

    monkeypatch.setattr(sys, "argv", [
        "tracker_replica.py",
        "--source", str(wrong),
        "--dest", str(secondary),
        "--context-check",
    ])

    assert tracker_replica.main() == 1
    assert (
        "does not match administrator"
        in capsys.readouterr().err
    )
    assert list(primary.iterdir()) == []
    assert list(secondary.iterdir()) == []


def test_actual_scoped_replication_uses_validated_roots(roots):
    data, _, primary, secondary = roots
    archive = backup.create_backup(data, primary)

    selected = administrator_replication_context413()
    result = tracker_replica.replicate(
        selected.primary,
        selected.secondary,
        keep=2,
    )

    assert result["copied"] == 1
    assert (
        (secondary / archive.name).read_bytes()
        == archive.read_bytes()
    )
    assert (data / "tracker.db").is_file()


def test_secondary_accounts_stay_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
