"""Release 440 secondary readiness, lockdown and session security gates.

The full private end-to-end workflow runs independently in
test_secondary_private_workflow440.py, allowing safe xdist loadfile sharding.
"""
import sqlite3
from contextlib import closing
from copy import deepcopy

import pytest

from app import config, session_auth385 as auth, secondary_preview430 as gateway
from scripts.secondary_integration440_support import (
    FEATURES, browser, _hidden, _login, _row, _counts,
)

def test_authenticated_readiness_matches_every_runtime_flag(browser, monkeypatch):
    client, root = browser
    anonymous = client.get("/secondary/readiness", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/secondary/login"

    _login(client, 2)

    # Obtain a real, independently validated worker response for this
    # authenticated secondary account. The only fixture substitution below
    # reuses this read-only count snapshot while testing feature-flag HTML.
    # It never substitutes for session/identity checks or write requests.
    private_report = {}
    actual_worker = gateway.read_workspace_overview429

    def capture_verified_report(uid):
        report = actual_worker(uid)
        private_report["uid"] = uid
        private_report["result"] = deepcopy(report)
        return report

    with monkeypatch.context() as capture:
        capture.setattr(
            gateway, "read_workspace_overview429", capture_verified_report
        )
        page = client.get("/secondary/readiness")

    assert page.status_code == 200
    assert private_report["uid"] == 2
    assert private_report["result"]["user_id"] == 2
    assert private_report["result"]["workspace_status"] == "inactive"
    assert private_report["result"]["login_enabled"] is False
    assert private_report["result"]["http_listener_started"] is False

    def stable_worker_report(uid):
        # Keep fail-closed account binding even for this test-only snapshot.
        if type(uid) is not int or uid != 2:
            raise PermissionError("Unexpected workspace identity")
        return deepcopy(private_report["result"])

    # The test-only return value is bound to the authenticated user and is
    # immutable across GETs; a modified copy cannot poison later requests.
    with pytest.raises(PermissionError):
        stable_worker_report(3)
    snapshot_copy = stable_worker_report(2)
    snapshot_copy["counts"].clear()
    assert stable_worker_report(2)["counts"] == private_report["result"]["counts"]

    assert page.headers["cache-control"] == "no-store"
    assert 'href="/secondary/readiness"' in client.get(
        "/secondary/overview"
    ).text
    assert "secondary workspace 2" in page.text.lower()
    assert "normal Tracker multi-user login" in page.text
    assert str(root) not in page.text
    assert "secondary-secure-password-2-440" not in page.text

    for flag, name, route in FEATURES:
        assert "Enabled (DEV)" in _row(page.text, name)
        monkeypatch.delenv(flag, raising=False)
        with monkeypatch.context() as pinned_readonly:
            pinned_readonly.setattr(
                gateway, "read_workspace_overview429", stable_worker_report
            )
            disabled = client.get("/secondary/readiness")
        assert disabled.status_code == 200
        assert "Disabled" in _row(disabled.text, name)
        assert "Enabled (DEV)" not in _row(disabled.text, name)
        # Exercise the actual fail-closed write route without any worker stub.
        assert client.post(route, data={}).status_code == 404
        monkeypatch.setenv(flag, "1")
        with monkeypatch.context() as pinned_readonly:
            pinned_readonly.setattr(
                gateway, "read_workspace_overview429", stable_worker_report
            )
            enabled = client.get("/secondary/readiness")
        assert "Enabled (DEV)" in _row(enabled.text, name)

    # End with an independent, real worker invocation after every flag
    # toggle. This still tests production readiness and account identity.
    final_page = client.get("/secondary/readiness")
    assert final_page.status_code == 200
    assert "secondary workspace 2" in final_page.text.lower()
    for _, name, _ in FEATURES:
        assert "Enabled (DEV)" in _row(final_page.text, name)


def test_gateway_emergency_lockdown_denies_every_preview_route(browser, monkeypatch):
    client, root = browser
    _login(client, 2)
    assert client.get("/secondary/readiness").status_code == 200
    before = _counts(root, 2)
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    for path in (
        "/secondary/login", "/secondary/overview",
        "/secondary/readiness", "/secondary/vitals",
        "/secondary/doses", "/secondary/inventory",
        "/secondary/reconstitution", "/secondary/reconcile",
        "/secondary/supplies", "/secondary/supplies/use",
    ):
        assert client.get(path).status_code == 404
    for _, _, route in FEATURES:
        assert client.post(route, data={}).status_code == 404
    assert _counts(root, 2) == before
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    assert client.get("/secondary/readiness").status_code == 200


def test_revoked_sessions_and_tampered_workspace_fail_closed(browser):
    client, root = browser
    _login(client, 2)
    page = client.get("/secondary/overview")
    logout = client.post(
        "/secondary/logout",
        data={"csrf_token": _hidden(page.text, "csrf_token")},
        follow_redirects=False,
    )
    assert logout.status_code == 303
    assert client.get(
        "/secondary/readiness", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies/use", data={}).status_code == 401
    _login(client, 2)
    with sqlite3.connect(
        root / "users" / "2" / "tracker.db",
    ) as db:
        db.execute(
            "UPDATE tracker_staged_workspace426 SET user_id=3"
        )
    assert client.get(
        "/secondary/readiness", follow_redirects=False,
    ).status_code == 303
    with closing(auth.connect()) as db:
        assert db.execute("""
            SELECT enabled FROM users WHERE id=2
        """).fetchone() == (0,)
        assert db.execute("""
            SELECT COUNT(*) FROM sessions WHERE user_id>1
        """).fetchone() == (0,)


def test_prod_and_master_disable_all_readiness(browser, monkeypatch):
    client, _ = browser
    _login(client, 2)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/readiness").status_code == 404
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.delenv("TRACKER_SECONDARY_PREVIEW430", raising=False)
    assert client.get("/secondary/readiness").status_code == 404


def test_no_query_params_and_readiness_never_changes_private_records(browser):
    client, root = browser
    _login(client, 2)
    before = _counts(root, 2)
    for path in (
        "/secondary/readiness?user_id=3",
        "/secondary/readiness?database=other",
    ):
        assert client.get(path).status_code == 400
    assert client.get("/secondary/readiness").status_code == 200
    assert client.get("/secondary/readiness").status_code == 200
    assert _counts(root, 2) == before
    assert all(value == 0 for value in _counts(root, 3).values())
