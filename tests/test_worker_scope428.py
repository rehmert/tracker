"""Release 428: feature router contracts and private-process isolation."""

import sqlite3
import subprocess
import sys

import pytest

from app import config, session_auth385 as auth
from app.user_bootstrap426 import (
    initialize_staged_workspace426,
)
from app.user_accounts427 import (
    stage_secondary_account427,
    inspect_staged_account427,
)
from app.user_storage388 import live_storage_for
from app.worker_scope428 import (
    SOURCE_ROOT,
    worker_plan428,
    worker_environment428,
    run_worker_probe428,
)
from app.worker_probe428 import verify_feature_routes428


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "DATA_DIR", tmp_path
    )
    monkeypatch.setattr(
        config, "instance_label",
        lambda: "DEV",
    )

    auth.bootstrap(
        "operator",
        "admin-secure-password-428",
    )

    (tmp_path / auth.FLAG).write_text(
        "enabled"
    )

    for uid in (2, 3):
        initialize_staged_workspace426(
            uid, tmp_path
        )
        stage_secondary_account427(
            uid,
            f"member-{uid}",
            f"secondary-secure-password-{uid}-428",
        )

    return tmp_path


def test_feature_router_contract_not_app_routes_placeholder():
    assert verify_feature_routes428() == 3


def test_private_environment_rejects_inherited_credentials(
    staged, monkeypatch
):
    monkeypatch.setenv(
        "TRACKER_PASS",
        "inherited-admin-password",
    )
    monkeypatch.setenv(
        "TRACKER_SESSION_OVERRIDE",
        "unsafe",
    )

    environment = worker_environment428(
        2, staged
    )

    assert environment["TRACKER_DATA_DIR"] == str(
        staged / "users" / "2"
    )

    assert environment["TRACKER_BACKUP_DIR"] == str(
        staged / "users" / "2" / "backups"
    )

    assert (
        environment["TRACKER_PASS"]
        != "inherited-admin-password"
    )

    assert len(environment["TRACKER_PASS"]) >= 40
    assert (
        "TRACKER_SESSION_OVERRIDE"
        not in environment
    )
    assert environment["TRACKER_CSRF_ENFORCE"] == "1"


def test_two_users_are_read_independently_in_child_processes(staged):
    first_database = (
        staged / "users" / "2" / "tracker.db"
    )

    with sqlite3.connect(first_database) as connection:
        connection.execute("""
            INSERT INTO compounds
                (name,category,notes,primary_unit)
            VALUES
                ('private-compound','other','','mg')
        """)

    first = run_worker_probe428(2, staged)
    second = run_worker_probe428(3, staged)

    assert first["private_compound_records"] == 1
    assert second["private_compound_records"] == 0

    for report in (first, second):
        assert report["storage_isolated"] is True
        assert report["feature_routes_verified"] == 3
        assert report["app_health_paths_present"] is True
        assert report["database_engines_inspected"] >= 3
        assert report["http_listener_started"] is False
        assert report["account_login_enabled"] is False


def test_worker_stays_inactive_and_unroutable(staged):
    report = run_worker_probe428(2, staged)

    assert report["account_login_enabled"] is False

    assert inspect_staged_account427(
        2, staged
    )["credential_status"] == "disabled"

    with pytest.raises(PermissionError):
        live_storage_for(2)


def run_invalid(environment):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "app.worker_probe428",
        ],
        cwd=SOURCE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )


def test_identity_swap_rejected(staged):
    environment = worker_environment428(
        2, staged
    )
    environment["TRACKER_DATA_DIR"] = str(
        staged / "users" / "3"
    )

    result = run_invalid(environment)

    assert result.returncode != 0
    assert (
        "Worker data directory does not match identity"
        in result.stderr
    )


def test_missing_secret_rejected(staged):
    environment = worker_environment428(
        2, staged
    )
    del environment["TRACKER_PASS"]

    result = run_invalid(environment)

    assert result.returncode != 0
    assert (
        "Dedicated worker authentication required"
        in result.stderr
    )


def test_disabled_csrf_rejected(staged):
    environment = worker_environment428(
        2, staged
    )
    environment["TRACKER_CSRF_ENFORCE"] = "0"

    result = run_invalid(environment)

    assert result.returncode != 0
    assert (
        "Worker browser-write protections disabled"
        in result.stderr
    )


def test_admin_and_missing_account_cannot_probe(staged):
    with pytest.raises(PermissionError):
        worker_plan428(1, staged)

    with pytest.raises(RuntimeError):
        worker_plan428(4, staged)


def test_prod_worker_denied(staged, monkeypatch):
    monkeypatch.setattr(
        config,
        "instance_label",
        lambda: "PROD",
    )

    with pytest.raises(PermissionError):
        worker_plan428(2, staged)


def test_probe_report_has_no_secrets(staged):
    report = run_worker_probe428(
        2, staged
    )

    assert not {
        "password",
        "secret",
        "token",
        "authorization",
    } & set(report)
