"""Release 415: administrator SQLite maintenance context preflight.

All database fixtures use temporary SQLite files.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import backup, config
from scripts import tracker_db_maintenance as maintenance


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()

    database = data / "tracker.db"

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sample (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sample VALUES ('admin-only')"
        )

    archives = tmp_path / "archives"
    archives.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", database)
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{database}",
    )
    monkeypatch.setattr(backup, "BACKUP_DIR", archives)

    return data, database, archives


def invoke(monkeypatch, *arguments):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tracker_db_maintenance.py", *arguments],
    )
    return maintenance.main()


def test_context_check_is_read_only(
    configured, monkeypatch, capsys
):
    data, database, archives = configured

    before = database.read_bytes()
    files_before = (
        set(data.iterdir()),
        set(archives.iterdir()),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Maintenance database operation must not run"
        )

    monkeypatch.setattr(
        maintenance,
        "connect_readonly",
        forbidden,
    )
    monkeypatch.setattr(
        maintenance,
        "snapshot",
        forbidden,
    )

    assert invoke(
        monkeypatch,
        "context-check",
    ) == 0

    assert (
        "PASS: Administrator maintenance context valid"
        in capsys.readouterr().out
    )

    assert database.read_bytes() == before
    assert files_before == (
        set(data.iterdir()),
        set(archives.iterdir()),
    )


def test_matching_explicit_database_is_accepted(
    configured, monkeypatch, capsys
):
    _, database, _ = configured

    assert invoke(
        monkeypatch,
        "context-check",
        "--database",
        str(database),
    ) == 0

    assert (
        str(database)
        in capsys.readouterr().out
    )


def test_cross_workspace_database_is_rejected(
    configured, monkeypatch, tmp_path
):
    _, database, archives = configured

    other = tmp_path / "other"
    other.mkdir()

    other_database = other / "tracker.db"

    with sqlite3.connect(other_database) as connection:
        connection.execute(
            "CREATE TABLE other (id INTEGER)"
        )

    original_bytes = database.read_bytes()
    other_bytes = other_database.read_bytes()

    with pytest.raises(
        ValueError,
        match="does not match administrator",
    ):
        invoke(
            monkeypatch,
            "context-check",
            "--database",
            str(other_database),
        )

    assert database.read_bytes() == original_bytes
    assert other_database.read_bytes() == other_bytes
    assert list(archives.iterdir()) == []


def test_database_url_mismatch_is_rejected(
    configured, monkeypatch, tmp_path
):
    _, database, archives = configured

    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{tmp_path / 'wrong.db'}",
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        invoke(
            monkeypatch,
            "context-check",
        )

    assert database.is_file()
    assert list(archives.iterdir()) == []


def test_symlinked_database_is_rejected(
    configured, monkeypatch
):
    data, database, _ = configured

    alias = data / "alias.db"
    alias.symlink_to(database)

    monkeypatch.setattr(
        config,
        "DB_PATH",
        alias,
    )
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{alias}",
    )

    with pytest.raises(ValueError, match="Symlinked"):
        invoke(
            monkeypatch,
            "context-check",
        )


def test_context_check_rejects_output_argument(
    configured, monkeypatch, tmp_path, capsys
):
    output = tmp_path / "should-not-exist.json"

    with pytest.raises(SystemExit) as caught:
        invoke(
            monkeypatch,
            "context-check",
            "--output",
            str(output),
        )

    assert caught.value.code == 2
    assert not output.exists()

    assert (
        "not supported"
        in capsys.readouterr().err
    )


def test_existing_check_requires_database(
    configured, monkeypatch
):
    with pytest.raises(SystemExit) as caught:
        invoke(monkeypatch, "check")

    assert caught.value.code == 2


def test_existing_selftest_remains_functional(
    configured, monkeypatch, capsys
):
    assert invoke(monkeypatch, "selftest") == 0

    assert (
        "Maintenance self-test: PASS"
        in capsys.readouterr().out
    )


def test_direct_script_works_without_pythonpath(
    configured, tmp_path
):
    data, database, archives = configured
    before = database.read_bytes()

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["TRACKER_DATA_DIR"] = str(data)
    environment["TRACKER_BACKUP_DIR"] = str(archives)

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(
                ROOT
                / "scripts"
                / "tracker_db_maintenance.py"
            ),
            "context-check",
            "--database",
            str(database),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )

    assert (
        "PASS: Administrator maintenance context valid"
        in result.stdout
    )

    assert database.read_bytes() == before
    assert list(archives.iterdir()) == []


def test_disabled_users_stay_denied():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
