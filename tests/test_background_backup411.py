"""Release 411: scheduled backup context and retention boundaries."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import tracker_backup


@pytest.fixture
def context(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "tracker.db"
    database.write_bytes(b"test-placeholder")

    archive_dir = tmp_path / "backups"
    archive_dir.mkdir()

    value = SimpleNamespace(
        user_id=1,
        scope="legacy-admin-instance",
        data_dir=data,
        database=database,
        backup_dir=archive_dir,
    )

    monkeypatch.setattr(
        tracker_backup,
        "administrator_context410",
        lambda: value,
    )

    return value


def run_create(monkeypatch):
    monkeypatch.setattr(
        tracker_backup.sys,
        "argv",
        ["tracker_backup", "create"],
    )
    tracker_backup.main()


def test_create_uses_same_context_for_backup_and_prune(
    context, monkeypatch
):
    events = []
    archive = context.backup_dir / "tracker-test.zip"
    archive.write_bytes(b"isolated-mock-archive")

    def create_backup(*, data_dir, backup_dir):
        events.append(("create", data_dir, backup_dir))
        return archive

    def verify_restorable(selected):
        events.append(("verify", selected))

    def prune_backups(*, backup_dir):
        events.append(("prune", backup_dir))
        return []

    monkeypatch.setattr(
        tracker_backup, "create_backup", create_backup
    )
    monkeypatch.setattr(
        tracker_backup, "verify_restorable", verify_restorable
    )
    monkeypatch.setattr(
        tracker_backup, "prune_backups", prune_backups
    )

    run_create(monkeypatch)

    assert events == [
        ("create", context.data_dir, context.backup_dir),
        ("verify", archive),
        ("prune", context.backup_dir),
    ]


def test_invalid_context_cannot_create_or_prune(
    monkeypatch
):
    events = []

    def deny():
        raise ValueError("Mismatched storage")

    monkeypatch.setattr(
        tracker_backup, "administrator_context410", deny
    )
    monkeypatch.setattr(
        tracker_backup,
        "create_backup",
        lambda **kwargs: events.append("create"),
    )
    monkeypatch.setattr(
        tracker_backup,
        "prune_backups",
        lambda **kwargs: events.append("prune"),
    )

    with pytest.raises(ValueError, match="Mismatched"):
        run_create(monkeypatch)

    assert events == []


def test_failed_restore_never_prunes(
    context, monkeypatch
):
    archive = context.backup_dir / "tracker-test.zip"
    archive.write_bytes(b"isolated-mock-archive")

    monkeypatch.setattr(
        tracker_backup,
        "create_backup",
        lambda **kwargs: archive,
    )

    def failed_restore(_):
        raise RuntimeError("Restore failed")

    monkeypatch.setattr(
        tracker_backup,
        "verify_restorable",
        failed_restore,
    )

    def unexpected_prune(**kwargs):
        raise AssertionError("Prune must not run")

    monkeypatch.setattr(
        tracker_backup, "prune_backups", unexpected_prune
    )

    with pytest.raises(RuntimeError, match="Restore failed"):
        run_create(monkeypatch)

    assert archive.exists()


def test_backup_from_wrong_directory_is_rejected(
    context, monkeypatch, tmp_path
):
    wrong = tmp_path / "wrong"
    wrong.mkdir()

    archive = wrong / "tracker-test.zip"
    archive.write_bytes(b"isolated-mock-archive")

    monkeypatch.setattr(
        tracker_backup,
        "create_backup",
        lambda **kwargs: archive,
    )

    monkeypatch.setattr(
        tracker_backup,
        "verify_restorable",
        lambda _: (_ for _ in ()).throw(
            AssertionError("Must not verify wrong archive")
        ),
    )

    monkeypatch.setattr(
        tracker_backup,
        "prune_backups",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Must not prune")
        ),
    )

    with pytest.raises(ValueError, match="outside authorized"):
        run_create(monkeypatch)


def test_symlinked_archive_is_rejected(
    context, monkeypatch, tmp_path
):
    target = tmp_path / "outside.zip"
    target.write_bytes(b"outside")

    alias = context.backup_dir / "tracker-alias.zip"
    alias.symlink_to(target)

    monkeypatch.setattr(
        tracker_backup,
        "create_backup",
        lambda **kwargs: alias,
    )

    monkeypatch.setattr(
        tracker_backup,
        "verify_restorable",
        lambda _: (_ for _ in ()).throw(
            AssertionError("Must not verify a symlink")
        ),
    )

    monkeypatch.setattr(
        tracker_backup,
        "prune_backups",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Must not prune")
        ),
    )

    with pytest.raises(ValueError, match="outside authorized"):
        run_create(monkeypatch)


def test_missing_archive_is_rejected(
    context, monkeypatch
):
    archive = context.backup_dir / "missing.zip"

    monkeypatch.setattr(
        tracker_backup,
        "create_backup",
        lambda **kwargs: archive,
    )

    monkeypatch.setattr(
        tracker_backup,
        "verify_restorable",
        lambda _: (_ for _ in ()).throw(
            AssertionError("Must not verify missing archive")
        ),
    )

    monkeypatch.setattr(
        tracker_backup,
        "prune_backups",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Must not prune")
        ),
    )

    with pytest.raises(ValueError, match="outside authorized"):
        run_create(monkeypatch)


def test_secondary_context_remains_disabled():
    from app.background_storage410 import (
        administrator_context410,
    )

    for user_id in (0, 2, 3, True, "1"):
        with pytest.raises(PermissionError):
            administrator_context410(user_id)
