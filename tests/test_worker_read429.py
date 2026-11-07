"""Release 429: fail-closed read-only worker and parent validation."""

import sqlite3
import subprocess
import sys

import pytest

from app import config, session_auth385 as auth
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import (
    inspect_staged_account427,
    stage_secondary_account427,
)
from app.user_storage388 import live_storage_for
from app.worker_read429 import COUNT_TABLES, parse_request429
from app.worker_request429 import read_workspace_overview429
from app.worker_scope428 import SOURCE_ROOT, worker_environment428


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")

    auth.bootstrap(
        "operator",
        "administrator-secure-password-429",
    )

    (tmp_path / auth.FLAG).write_text("enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)

        stage_secondary_account427(
            uid,
            f"member-{uid}",
            f"secondary-secure-password-{uid}-429",
        )

    return tmp_path


def child_request(environment, payload='{"action":"overview"}'):
    return subprocess.run(
        [sys.executable, "-m", "app.worker_read429"],
        input=payload,
        cwd=SOURCE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )


def test_request_schema_is_strict_and_allowlisted():
    assert parse_request429(
        b'{"action":"overview"}'
    ) == "overview"

    for raw in (
        b'',
        b'not-json',
        b'[]',
        b'null',
        b'{"action":"query"}',
        b'{"action":"overview","user_id":3}',
        b'{"action":"overview","database":"/tmp/db"}',
        b'{"action":"overview","sql":"SELECT * FROM users"}',
        b'{"action":"overview","action":"overview"}',
        b'x' * 2049,
    ):
        with pytest.raises(ValueError):
            parse_request429(raw)


def test_users_have_disjoint_database_overviews(staged):
    with sqlite3.connect(
        staged / "users" / "2" / "tracker.db"
    ) as db:
        db.execute("""
            INSERT INTO compounds
                (name,category,notes,primary_unit)
            VALUES ('private-two','other','','mg')
        """)

        db.execute("""
            INSERT INTO tracker_water_entries(logged_on,ounces)
            VALUES ('2026-11-05',16)
        """)

    with sqlite3.connect(
        staged / "users" / "3" / "tracker.db"
    ) as db:
        db.execute("""
            INSERT INTO tracker_water_entries(logged_on,ounces)
            VALUES ('2026-11-05',32)
        """)

    left = read_workspace_overview429(2, staged)
    right = read_workspace_overview429(3, staged)

    assert left["user_id"] == 2
    assert right["user_id"] == 3

    assert left["counts"]["compounds"] == 1
    assert right["counts"]["compounds"] == 0

    assert left["counts"]["water_entries"] == 1
    assert right["counts"]["water_entries"] == 1

    assert (
        set(left["counts"])
        == set(right["counts"])
        == set(COUNT_TABLES)
    )

    for report in (left, right):
        assert report["mode"] == "offline-readonly-worker"
        assert report["workspace_status"] == "inactive"
        assert report["http_listener_started"] is False
        assert report["login_enabled"] is False


def test_forged_identity_or_sql_cannot_be_requested(staged):
    environment = worker_environment428(2, staged)

    for payload in (
        '{"action":"overview","user_id":3}',
        '{"action":"overview","database":"/tmp/fake.db"}',
        '{"action":"overview","sql":"DROP TABLE compounds"}',
        '{"action":"get_accounts"}',
    ):
        result = child_request(environment, payload)

        assert result.returncode != 0
        assert not result.stdout.strip()


def test_swapping_private_path_fails_before_database_reads(staged):
    environment = worker_environment428(2, staged)
    environment["TRACKER_DATA_DIR"] = str(
        staged / "users" / "3"
    )

    result = child_request(environment)

    assert result.returncode != 0
    assert (
        "Worker data directory does not match identity"
        in result.stderr
    )


def test_parent_rejects_tampered_workspace_before_child_launch(staged):
    with sqlite3.connect(
        staged / "users" / "2" / "tracker.db"
    ) as db:
        db.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)

    with pytest.raises(
        RuntimeError,
        match="Workspace identity or inactive marker mismatch",
    ):
        worker_environment428(2, staged)

    with pytest.raises(
        RuntimeError,
        match="Workspace identity or inactive marker mismatch",
    ):
        read_workspace_overview429(2, staged)


def test_child_rejects_tampered_workspace_even_with_prior_valid_environment(
    staged,
):
    # Prepare a valid environment BEFORE altering the identity marker.
    environment = worker_environment428(2, staged)

    with sqlite3.connect(
        staged / "users" / "2" / "tracker.db"
    ) as db:
        db.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)

    result = child_request(environment)

    assert result.returncode != 0
    assert "Workspace identity mismatch" in result.stderr
    assert not result.stdout.strip()


def test_secondary_login_and_live_access_remain_disabled(staged):
    read_workspace_overview429(2, staged)

    assert inspect_staged_account427(
        2, staged
    )["credential_status"] == "disabled"

    assert not auth.verify_admin(
        "member-2",
        "secondary-secure-password-2-429",
    )

    with pytest.raises(PermissionError):
        live_storage_for(2)

    with pytest.raises(PermissionError):
        read_workspace_overview429(1, staged)


def test_missing_staged_workspace_is_denied(staged):
    with pytest.raises(RuntimeError):
        read_workspace_overview429(4, staged)


def test_worker_overview_does_not_mutate_workspaces(staged):
    path = staged / "users" / "2" / "tracker.db"

    with sqlite3.connect(path) as db:
        before = db.execute(
            "SELECT count(*) FROM compounds"
        ).fetchone()[0]

    read_workspace_overview429(2, staged)

    with sqlite3.connect(path) as db:
        after = db.execute(
            "SELECT count(*) FROM compounds"
        ).fetchone()[0]

    assert before == after
