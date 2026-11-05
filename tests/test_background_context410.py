"""Release 410: administrator background-storage validation."""

from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy.engine import make_url

from app import backup, config
from app import background_storage410 as storage


@pytest.fixture
def configured(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()

    database = data / "tracker.db"
    database.write_bytes(b"isolated-test-placeholder")

    archives = tmp_path / "archives"

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", database)
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{database}",
    )
    monkeypatch.setattr(backup, "BACKUP_DIR", archives)

    return data, database, archives


def test_valid_admin_context_is_immutable(configured):
    data, database, archives = configured

    context = storage.administrator_context410()

    assert context.user_id == 1
    assert context.scope == "legacy-admin-instance"
    assert context.data_dir == data
    assert context.database == database
    assert context.backup_dir == archives

    with pytest.raises(FrozenInstanceError):
        context.user_id = 2


@pytest.mark.parametrize(
    "user_id",
    [0, 2, 3, -1, "1", True, None],
)
def test_other_identities_are_denied(configured, user_id):
    with pytest.raises(PermissionError):
        storage.administrator_context410(user_id)


def test_database_url_mismatch_is_rejected(
    configured, monkeypatch
):
    data, _, _ = configured

    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{data / 'different.db'}",
    )

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_database_path_mismatch_is_rejected(
    configured, monkeypatch
):
    data, _, _ = configured

    monkeypatch.setattr(
        config,
        "DB_PATH",
        data / "unexpected.db",
    )

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_symlinked_database_is_rejected(
    configured, monkeypatch
):
    data, database, _ = configured
    alias = data / "alias.db"
    alias.symlink_to(database)

    monkeypatch.setattr(config, "DB_PATH", alias)
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{alias}",
    )

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_symlinked_archive_directory_is_rejected(
    configured, monkeypatch, tmp_path
):
    _, _, archives = configured

    actual = tmp_path / "actual"
    actual.mkdir()
    archives.symlink_to(actual, target_is_directory=True)

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_missing_database_is_rejected(configured):
    _, database, _ = configured
    database.unlink()

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_non_sqlite_url_is_rejected(
    configured, monkeypatch
):
    monkeypatch.setattr(
        config,
        "DB_URL",
        "postgresql://localhost/tracker",
    )

    with pytest.raises(ValueError):
        storage.administrator_context410()


def test_validation_does_not_create_archive_directory(
    configured
):
    _, _, archives = configured
    assert not archives.exists()

    storage.administrator_context410()

    assert not archives.exists()


def test_existing_backup_functions_are_unchanged():
    import inspect

    assert "data_dir" in inspect.signature(
        backup.create_backup
    ).parameters

    assert "backup_dir" in inspect.signature(
        backup.create_backup
    ).parameters


def test_future_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
