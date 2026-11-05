"""Release 416: fail-closed administrator selection and maintenance outputs."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import backup, config
from scripts import tracker_db_maintenance as cli


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()

    db = data / "tracker.db"

    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sample(label TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO sample VALUES ('ADMIN416')"
        )

    backups = tmp_path / "backups"
    backups.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(
        config, "DB_URL", f"sqlite:///{db}"
    )
    monkeypatch.setattr(backup, "BACKUP_DIR", backups)

    return data, db, backups


def invoke(monkeypatch, *args):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tracker_db_maintenance", *args],
    )
    return cli.main()


def test_scoped_check_selects_admin_database(
    configured, monkeypatch, capsys
):
    _, db, backups = configured
    before = db.read_bytes()

    assert invoke(
        monkeypatch, "check", "--admin-scoped"
    ) == 0

    result = json.loads(capsys.readouterr().out)

    assert result["structural_integrity"]
    assert result["foreign_key_integrity"]
    assert db.read_bytes() == before
    assert list(backups.iterdir()) == []


def test_scoped_report_is_exclusive_and_contains_admin_data(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured
    target = tmp_path / "report.json"

    assert invoke(
        monkeypatch,
        "report", "--admin-scoped",
        "--output", str(target),
    ) == 0

    item = json.loads(target.read_text())

    assert item["metadata"]["database"] == str(db)
    assert any(
        x["table"] == "sample" and x["rows"] == 1
        for x in item["tables"]
    )

    before = target.read_bytes()

    with pytest.raises(FileExistsError, match="overwrite"):
        invoke(
            monkeypatch,
            "report", "--admin-scoped",
            "--output", str(target),
        )

    assert target.read_bytes() == before


def test_scoped_snapshot_copies_only_admin_database(
    configured, monkeypatch, tmp_path
):
    data, db, _ = configured
    target = tmp_path / "snapshot.db"
    before = db.read_bytes()

    assert invoke(
        monkeypatch,
        "snapshot", "--admin-scoped",
        "--output", str(target),
    ) == 0

    with sqlite3.connect(target) as conn:
        assert conn.execute(
            "SELECT label FROM sample"
        ).fetchone()[0] == "ADMIN416"

    assert db.read_bytes() == before
    assert set(data.iterdir()) == {db}


def test_other_database_rejected_before_any_maintenance(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured

    other = tmp_path / "other.db"
    with sqlite3.connect(other) as conn:
        conn.execute(
            "CREATE TABLE other(x INTEGER)"
        )

    before = (db.read_bytes(), other.read_bytes())

    for action in ("check", "report", "snapshot"):
        target = tmp_path / (action + ".out")
        args = [
            action, "--admin-scoped",
            "--database", str(other),
        ]

        if action != "check":
            args += ["--output", str(target)]

        with pytest.raises(
            ValueError, match="does not match administrator"
        ):
            invoke(monkeypatch, *args)

        assert not target.exists()

    assert (
        db.read_bytes(),
        other.read_bytes(),
    ) == before


def test_wrong_configured_database_rejected_before_report(
    configured, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        config,
        "DB_URL",
        f"sqlite:///{tmp_path / 'wrong.db'}",
    )

    target = tmp_path / "report.json"

    with pytest.raises(
        ValueError, match="does not match"
    ):
        invoke(
            monkeypatch,
            "report", "--admin-scoped",
            "--output", str(target),
        )

    assert not target.exists()


def test_protected_output_locations_are_rejected(
    configured, monkeypatch
):
    data, _, backups = configured

    for action in ("report", "snapshot"):
        for destination in (
            data / "output.tmp",
            backups / "output.tmp",
        ):
            with pytest.raises(
                ValueError, match="overlaps protected"
            ):
                invoke(
                    monkeypatch,
                    action,
                    "--admin-scoped",
                    "--output",
                    str(destination),
                )

            assert not destination.exists()


def test_symlink_and_relative_outputs_are_denied(
    configured, monkeypatch, tmp_path
):
    original = tmp_path / "original.json"
    original.write_text("unchanged")

    link = tmp_path / "alias.json"
    link.symlink_to(original)

    with pytest.raises(ValueError, match="Symlinked"):
        invoke(
            monkeypatch,
            "report", "--admin-scoped",
            "--output", str(link),
        )

    with pytest.raises(ValueError, match="absolute"):
        invoke(
            monkeypatch,
            "report", "--admin-scoped",
            "--output", "relative.json",
        )

    assert original.read_text() == "unchanged"


def test_existing_and_missing_parent_destinations_denied(
    configured, monkeypatch, tmp_path
):
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"keep")

    with pytest.raises(
        FileExistsError, match="overwrite"
    ):
        invoke(
            monkeypatch,
            "snapshot", "--admin-scoped",
            "--output", str(existing),
        )

    with pytest.raises(
        ValueError, match="already exist"
    ):
        invoke(
            monkeypatch,
            "report", "--admin-scoped",
            "--output",
            str(tmp_path / "missing" / "report.json"),
        )

    assert existing.read_bytes() == b"keep"


def test_legacy_modes_and_selftest_preserved(
    configured, monkeypatch, tmp_path, capsys
):
    _, db, _ = configured

    with pytest.raises(SystemExit):
        invoke(monkeypatch, "check")

    assert invoke(
        monkeypatch,
        "check",
        "--database",
        str(db),
    ) == 0

    assert invoke(monkeypatch, "selftest") == 0

    assert (
        "Maintenance self-test: PASS"
        in capsys.readouterr().out
    )

    with pytest.raises(SystemExit):
        invoke(
            monkeypatch, "selftest", "--admin-scoped"
        )

    with pytest.raises(SystemExit):
        invoke(
            monkeypatch, "context-check", "--admin-scoped"
        )


def test_scoped_command_direct_python_without_pythonpath(
    configured, tmp_path
):
    data, db, backups = configured

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["TRACKER_DATA_DIR"] = str(data)
    env["TRACKER_BACKUP_DIR"] = str(backups)

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(
                ROOT / "scripts" / "tracker_db_maintenance.py"
            ),
            "check",
            "--admin-scoped",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
    )

    assert result.returncode == 0, (
        result.stdout, result.stderr
    )

    assert json.loads(
        result.stdout
    )["structural_integrity"]

    assert db.is_file()


def test_secondary_accounts_remain_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
