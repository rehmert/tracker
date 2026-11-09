"""Release 433: DEV-only, authenticated, idempotent private vitals writes."""

import json
import re
import sqlite3
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426
from app.worker_scope428 import SOURCE_ROOT, worker_environment428
from app.worker_vital_write433 import (
    create_vital_for_user433,
    form_payload433,
    parse_vital433,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_VITAL_WRITES433", "1")

    auth.bootstrap("operator", "administrator-secure-password-433")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-433",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)

    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _token(html, name):
    match = re.search(
        rf'name="{re.escape(name)}"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, f"Missing {name} input"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    response = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-433",
            "csrf_token": _token(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response


def _vital_form(client):
    page = client.get("/secondary/vitals/new")
    assert page.status_code == 200
    assert 'action="/secondary/vitals/new"' in page.text
    return {
        "csrf_token": _token(page.text, "csrf_token"),
        "submission_token": _token(page.text, "submission_token"),
        "measured_at": "2026-11-05T10:15",
        "weight": "270.5",
        "weight_unit": "lb",
        "systolic": "124",
        "diastolic": "74",
        "pulse_bpm": "68",
        "context": "PRIVATE-SECONDARY",
        "notes": "PRIVATE-NOTES-433",
    }


def _rows(root, uid):
    with sqlite3.connect(
        root / "users" / str(uid) / "tracker.db",
    ) as connection:
        return connection.execute("""
            SELECT measured_at,weight_kg,systolic,diastolic,
                   pulse_bpm,context,notes
            FROM vital_readings ORDER BY id
        """).fetchall()


def test_valid_vital_write_affects_only_authenticated_user(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)
    response = client.post(
        "/secondary/vitals/new",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/secondary/vitals"

    first = _rows(root, 2)
    assert len(first) == 1
    assert abs(first[0][1] - 122.696) < 0.1
    assert first[0][2:5] == (124, 74, 68)
    assert first[0][5:] == ("PRIVATE-SECONDARY", "PRIVATE-NOTES-433")
    assert _rows(root, 3) == []
    assert not (root / "tracker.db").exists()

    recent = client.get("/secondary/vitals")
    assert recent.status_code == 200
    assert "PRIVATE-SECONDARY" in recent.text


def test_duplicate_token_is_rejected_without_second_insert(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    first = client.post(
        "/secondary/vitals/new", data=data, follow_redirects=False,
    )
    duplicate = client.post(
        "/secondary/vitals/new", data=data, follow_redirects=False,
    )

    assert first.status_code == 303
    assert duplicate.status_code == 409
    assert len(_rows(root, 2)) == 1

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db",
    ) as connection:
        assert connection.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_vital_create433'
        """).fetchone() == (1,)


def test_secondary_login_swaps_write_destination(browser):
    client, root = browser
    _login(client, 2)
    first = _vital_form(client)
    assert client.post(
        "/secondary/vitals/new", data=first, follow_redirects=False,
    ).status_code == 303

    _login(client, 3)
    second = _vital_form(client)
    second["context"] = "PRIVATE-THREE"
    assert client.post(
        "/secondary/vitals/new", data=second, follow_redirects=False,
    ).status_code == 303

    assert len(_rows(root, 2)) == 1
    assert len(_rows(root, 3)) == 1
    assert _rows(root, 2)[0][5] == "PRIVATE-SECONDARY"
    assert _rows(root, 3)[0][5] == "PRIVATE-THREE"


def test_csrf_forgery_and_cross_site_request_denied(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    forged = client.post(
        "/secondary/vitals/new",
        data={**data, "csrf_token": "forged"},
    )
    assert forged.status_code == 403

    cross_site = client.post(
        "/secondary/vitals/new",
        headers={"Sec-Fetch-Site": "cross-site"},
        data=data,
    )
    assert cross_site.status_code == 403
    assert _rows(root, 2) == []


def test_no_unauthorized_fields_or_mutation(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    for field, value in (
        ("user_id", "3"),
        ("database", "/opt/tracker/data/tracker.db"),
        ("sql", "DELETE FROM vital_readings"),
    ):
        reply = client.post(
            "/secondary/vitals/new", data={**data, field: value},
        )
        assert reply.status_code == 422

    assert client.post(
        "/secondary/vitals/new?user_id=3", data=data,
    ).status_code == 400

    assert client.get(
        "/secondary/vitals/new?user_id=3",
    ).status_code == 400
    assert _rows(root, 2) == []
    assert _rows(root, 3) == []


def test_invalid_reading_never_changes_database(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    invalid = [
        {"systolic": "145", "diastolic": ""},
        {"weight": "NaN"},
        {"weight": "-5"},
        {"weight": "1200"},
        {"systolic": "100", "diastolic": "180"},
        {"pulse_bpm": "9"},
        {"measured_at": "not-a-date"},
    ]

    for changes in invalid:
        response = client.post(
            "/secondary/vitals/new",
            data={**data, **changes},
        )
        assert response.status_code == 422, changes

    assert _rows(root, 2) == []


def test_write_disabled_by_default_and_for_production(browser, monkeypatch):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    monkeypatch.delenv("TRACKER_SECONDARY_VITAL_WRITES433")
    assert client.get("/secondary/vitals/new").status_code == 404
    assert client.post("/secondary/vitals/new", data=data).status_code == 404
    assert client.get("/secondary/vitals").status_code == 200
    assert _rows(root, 2) == []

    monkeypatch.setenv("TRACKER_SECONDARY_VITAL_WRITES433", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/vitals/new").status_code == 200
    assert client.post("/secondary/vitals/new", data=data).status_code == 403


def test_no_session_cannot_post(browser):
    client, root = browser
    data = {
        "csrf_token": "forged",
        "submission_token": "e3e70682-c209-4cac-a29f-6fbed82c07cd",
    }
    result = client.post("/secondary/vitals/new", data=data)
    assert result.status_code == 401
    assert _rows(root, 2) == []


def test_tampered_user_marker_is_rejected_before_write(browser):
    client, root = browser
    _login(client, 2)
    data = _vital_form(client)

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db",
    ) as connection:
        connection.execute(
            "UPDATE tracker_staged_workspace426 SET user_id=3"
        )

    result = client.post("/secondary/vitals/new", data=data)
    assert result.status_code == 401
    assert _rows(root, 2) == []


@pytest.mark.parametrize("payload", (
    b"",
    b"[]",
    b'{"action":"create_vital","user_id":3,"payload":{}}',
    b'{"action":"query","payload":{}}',
    b'{"action":"create_vital","payload":{"sql":"DROP TABLE users"}}',
    b'{"action":"create_vital","action":"create_vital","payload":{}}',
    b"x" * 4097,
))
def test_private_worker_rejects_forged_requests(payload):
    with pytest.raises(ValueError):
        parse_vital433(payload)


def test_direct_worker_rejects_path_swap(browser):
    _, root = browser
    env = worker_environment428(2, root)
    env["TRACKER_WORKER_VITAL_WRITE433"] = "1"
    env["TRACKER_DATA_DIR"] = str(root / "users" / "3")

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_vital_write433"],
        input="{}",
        env=env, cwd=SOURCE_ROOT,
        text=True, capture_output=True, timeout=45,
    )
    assert result.returncode != 0
    assert not result.stdout.strip()
    assert "Worker data directory does not match identity" in result.stderr


def test_parent_cannot_write_admin_or_when_disabled(browser, monkeypatch):
    _, root = browser
    with pytest.raises(PermissionError):
        create_vital_for_user433(1, {}, root)

    monkeypatch.delenv("TRACKER_SECONDARY_VITAL_WRITES433")
    with pytest.raises(PermissionError):
        create_vital_for_user433(2, {}, root)


def test_main_middleware_exemption_is_one_opt_in_path():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert "secondary_form_post433" in source
    assert 'request.url.path == "/secondary/vitals/new"' in source
    assert "vital_writes_enabled433()" in source
    assert "and not secondary_form_post433" in source
