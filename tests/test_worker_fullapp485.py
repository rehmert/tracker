"""Release 485: main Tracker app runs privately per staged user."""

import hashlib
import json
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
from app.worker_scope428 import SOURCE_ROOT, worker_environment428


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    auth.bootstrap("operator", "admin-password-485-rehearsal")
    (tmp_path / auth.FLAG).write_text("enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"private-password-485-{uid}"
        )
    return tmp_path


def _run(staged, uid, modify=None):
    env = worker_environment428(uid, staged)
    if modify:
        modify(env)
    return subprocess.run(
        [sys.executable, "-m", "app.worker_fullapp485"],
        cwd=SOURCE_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def test_full_app_runs_per_user_with_private_engines(staged):
    first_db = staged / "users" / "2" / "tracker.db"
    with sqlite3.connect(first_db) as db:
        db.execute("""
            INSERT INTO compounds (name,category,notes,primary_unit)
            VALUES ('user-two-only','other','','mg')
        """)

    auth_file = staged / auth.DATABASE
    before = hashlib.sha256(auth_file.read_bytes()).digest()
    reports = []
    for uid in (2, 3):
        result = _run(staged, uid)
        assert result.returncode == 0, result.stderr[-2500:]
        reports.append(json.loads(result.stdout))

    assert [x["user_id"] for x in reports] == [2, 3]
    assert [x["private_compound_count"] for x in reports] == [1, 0]
    assert hashlib.sha256(auth_file.read_bytes()).digest() == before
    for report in reports:
        assert report["mode"] == "offline-fullapp-private-worker485"
        assert report["full_app_routes_verified"] == 9
        assert report["basic_auth_required"] is True
        assert report["primary_engine_is_private"] is True
        assert report["food_engines_are_private"] is True
        assert report["http_listener_started"] is False
        assert report["account_activated"] is False
    for uid in (2, 3):
        assert inspect_staged_account427(uid, staged)["login_enabled"] is False
        with pytest.raises(PermissionError):
            live_storage_for(uid)


def test_worker_rejects_cross_account_path(staged):
    result = _run(
        staged, 2,
        lambda env: env.update({
            "TRACKER_DATA_DIR": str(staged / "users" / "3")
        }),
    )
    assert result.returncode != 0
    assert "Worker data directory does not match identity" in result.stderr
    assert not result.stdout.strip()


def test_worker_requires_protections_and_private_credentials(staged):
    for key, replacement in (
        ("TRACKER_PASS", ""),
        ("TRACKER_CSRF_ENFORCE", "0"),
        ("TRACKER_ORIGIN_GUARD", "0"),
    ):
        result = _run(
            staged, 2,
            lambda env: env.update({key: replacement}),
        )
        assert result.returncode != 0
        assert not result.stdout.strip()


def test_no_production_activation_paths(staged, monkeypatch):
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    with pytest.raises(PermissionError):
        worker_environment428(2, staged)
