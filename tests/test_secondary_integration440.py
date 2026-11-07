"""Release 440: secondary gateway readiness and full private workflow gate."""

import re
import sqlite3
from contextlib import closing
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426

FEATURES = (
    ("TRACKER_SECONDARY_VITAL_WRITES433", "vitals", "/secondary/vitals/new"),
    ("TRACKER_SECONDARY_DOSE_WRITES434", "doses", "/secondary/doses/new"),
    ("TRACKER_SECONDARY_INVENTORY_WRITES435", "inventory",
     "/secondary/inventory/compounds"),
    ("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", "reconstitution",
     "/secondary/reconstitution"),
    ("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "vial_corrections",
     "/secondary/reconcile/correct"),
    ("TRACKER_SECONDARY_SUPPLY_WRITES438", "supply_intake",
     "/secondary/supplies"),
    ("TRACKER_SECONDARY_SUPPLY_USE439", "supply_use",
     "/secondary/supplies/use"),
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    for flag, _, _ in FEATURES:
        monkeypatch.setenv(flag, "1")

    auth.bootstrap("operator", "administrator-secure-password-440")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-440",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, field):
    found = re.search(
        rf'name="{re.escape(field)}"\s+value="([^"]+)"',
        html,
    )
    assert found, f"Hidden field {field} not found"
    return found.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login", data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-440",
            "csrf_token": _hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def _post_form(client, page_path, action, fields):
    response = client.get(page_path)
    assert response.status_code == 200, (
        page_path, response.status_code, response.text[:200]
    )
    pattern = (
        r'<form\b[^>]*\baction="' + re.escape(action)
        + r'"[^>]*>(.*?)</form>'
    )
    found = re.search(pattern, response.text, flags=re.S)
    assert found, f"Form action {action} not found on {page_path}"
    inner = found.group(1)
    data = {
        "csrf_token": _hidden(inner, "csrf_token"),
        "submission_token": _hidden(inner, "submission_token"),
        **fields,
    }
    result = client.post(action, data=data, follow_redirects=False)
    assert result.status_code == 303, (
        action, result.status_code, result.text[:250]
    )
    return result


def _row(html, feature):
    found = re.search(
        rf'<tr data-feature="{re.escape(feature)}">(.*?)</tr>',
        html, flags=re.S,
    )
    assert found, f"Missing capability {feature}"
    return found.group(1)


def _counts(root, uid):
    path = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "compounds", "vials", "preparation_events", "dose_logs",
                "vital_readings", "supplies", "supply_usages",
                "preparation_supplies", "change_audit",
            )
        }


def test_authenticated_readiness_matches_every_runtime_flag(browser, monkeypatch):
    client, root = browser
    anonymous = client.get("/secondary/readiness", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/secondary/login"

    _login(client, 2)
    page = client.get("/secondary/readiness")
    assert page.status_code == 200
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
        disabled = client.get("/secondary/readiness")
        assert disabled.status_code == 200
        assert "Disabled" in _row(disabled.text, name)
        assert "Enabled (DEV)" not in _row(disabled.text, name)
        assert client.post(route, data={}).status_code == 404
        monkeypatch.setenv(flag, "1")
        assert "Enabled (DEV)" in _row(
            client.get("/secondary/readiness").text, name
        )


def test_full_private_browser_workflow_with_audits_and_no_cross_account_data(browser):
    client, root = browser
    _login(client, 2)

    _post_form(
        client, "/secondary/inventory", "/secondary/inventory/compounds",
        {
            "name": "PRIVATE-440-ALPHA", "category": "peptide",
            "primary_unit": "mg", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/inventory", "/secondary/inventory/vials",
        {
            "compound_id": "1", "label": "PRIVATE-440-VIAL",
            "content_value": "10", "content_unit": "mg",
            "form": "lyophilized", "volume_ml": "", "lot": "440",
            "cap_color": "Blue", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/reconstitution", "/secondary/reconstitution",
        {"vial_id": "1", "volume_ml": "2"},
    )
    _post_form(
        client, "/secondary/doses/new", "/secondary/doses/new",
        {
            "vial_id": "1",
            "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "amount": "2", "unit": "mg",
            "site": "", "notes": "PRIVATE-440-DOSE",
        },
    )
    _post_form(
        client, "/secondary/vitals/new", "/secondary/vitals/new",
        {
            "measured_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "weight": "240", "weight_unit": "lb",
            "systolic": "122", "diastolic": "78",
            "pulse_bpm": "67", "context": "PRIVATE-440-VITAL",
            "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies", "/secondary/supplies",
        {
            "name": "PRIVATE-440-BAC", "kind": "bac_water",
            "quantity": "5", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies", "/secondary/supplies",
        {
            "name": "PRIVATE-440-NEEDLE", "kind": "needle",
            "quantity": "10", "notes": "",
        },
    )
    _post_form(
        client, "/secondary/supplies/use", "/secondary/supplies/use",
        {
            "supply_id": "1", "reference": "reconstitution:1",
            "amount": "2", "notes": "Water actually consumed",
        },
    )
    _post_form(
        client, "/secondary/supplies/use", "/secondary/supplies/use",
        {
            "supply_id": "2", "reference": "dose:1",
            "amount": "1", "notes": "Needle actually consumed",
        },
    )

    correction_page = client.get("/secondary/reconcile/vials/1")
    assert correction_page.status_code == 200
    assert "8 mg" in correction_page.text
    _post_form(
        client, "/secondary/reconcile/vials/1", "/secondary/reconcile/correct",
        {
            "vial_id": "1",
            "snapshot": _hidden(correction_page.text, "snapshot"),
            "label": "PRIVATE-440-CORRECTED",
            "lot": "440", "cap_color": "Blue",
            "status": "in_use",
            "reason": "Physical vial label verified",
        },
    )

    for route, expected in (
        ("/secondary/overview", "Private Workspace Overview"),
        ("/secondary/vitals", "PRIVATE-440-VITAL"),
        ("/secondary/doses", "PRIVATE-440-ALPHA"),
        ("/secondary/inventory", "PRIVATE-440-CORRECTED"),
        ("/secondary/reconcile", "8 mg"),
        ("/secondary/supplies", "PRIVATE-440-BAC"),
        ("/secondary/supplies/use", "Reconstitution #1"),
        ("/secondary/readiness", "Workspace Readiness"),
    ):
        page = client.get(route)
        assert page.status_code == 200, (route, page.status_code)
        assert expected in page.text, (route, expected)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        vial = db.execute("""
            SELECT status,label,volume_ml FROM vials
            WHERE id=1
        """).fetchone()
        supplies = db.execute("""
            SELECT id,remaining_qty FROM supplies ORDER BY id
        """).fetchall()
        usage_links = db.execute(
            "SELECT COUNT(*) FROM preparation_supplies"
        ).fetchone()[0]
        audits = db.execute("""
            SELECT action FROM change_audit ORDER BY id
        """).fetchall()
        assert vial == ("in_use", "PRIVATE-440-CORRECTED", 2.0)
        assert supplies == [(1, 3.0), (2, 9.0)]
        assert usage_links == 1
        assert [r[0] for r in audits] == [
            "secondary_supply_intake438",
            "secondary_supply_intake438",
            "secondary_supply_use439",
            "secondary_supply_use439",
            "secondary_correction437",
        ]

    assert _counts(root, 2)["dose_logs"] == 1
    assert _counts(root, 2)["vital_readings"] == 1
    assert all(value == 0 for value in _counts(root, 3).values())
    assert not (root / "tracker.db").exists()

    _login(client, 3)
    for route, secret in (
        ("/secondary/inventory", "PRIVATE-440-ALPHA"),
        ("/secondary/doses", "PRIVATE-440-ALPHA"),
        ("/secondary/vitals", "PRIVATE-440-VITAL"),
        ("/secondary/supplies", "PRIVATE-440-BAC"),
        ("/secondary/reconcile", "PRIVATE-440-CORRECTED"),
    ):
        page = client.get(route)
        assert page.status_code == 200
        assert secret not in page.text


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
