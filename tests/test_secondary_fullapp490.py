"""Release 490: private primary vitals logging, two-user isolation and guards."""

import re
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def browser490(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_VITAL_WRITES433", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_VITAL_WRITES490", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    auth.bootstrap("admin490", "secure-admin-password-490")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-password-{uid}-secure-490",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def hidden(html, key):
    result = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"', html
    )
    assert result is not None, f"Missing hidden input: {key}"
    return result.group(1)


def login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-password-{uid}-secure-490",
            "csrf_token": hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def vital_payload(page, context="PRIVATE-TWO-490"):
    assert page.status_code == 200, page.text[-700:]
    assert 'action="/secondary/full/vitals"' in page.text
    return {
        "csrf_token": hidden(page.text, "csrf_token"),
        "submission_token": hidden(page.text, "submission_token"),
        "measured_at": "2026-11-05T10:15",
        "weight": "270.5",
        "weight_unit": "lb",
        "systolic": "124",
        "diastolic": "74",
        "pulse_bpm": "68",
        "context": context,
        "notes": "private vital from primary preview",
    }


def private_rows(root, uid):
    path = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(path) as db:
        return db.execute("""
            SELECT measured_at,weight_kg,systolic,diastolic,
                   pulse_bpm,context,notes
            FROM vital_readings ORDER BY id
        """).fetchall()


def test_private_vital_create_and_read_is_isolated(browser490):
    client, root = browser490
    login(client, 2)
    page = client.get("/secondary/full/vitals")
    assert page.status_code == 200
    assert "form-action 'self'" in page.headers["content-security-policy"]
    assert "secure" in page.headers["set-cookie"].lower()
    first = vital_payload(page)

    result = client.post(
        "/secondary/full/vitals",
        data=first, follow_redirects=False,
    )
    assert result.status_code == 303, result.text[-800:]
    assert result.headers["location"] == "/secondary/full/vitals"
    assert len(private_rows(root, 2)) == 1
    assert private_rows(root, 3) == []
    assert not (root / "tracker.db").exists()

    saved = private_rows(root, 2)[0]
    assert abs(saved[1] - 122.696) < 0.1
    assert saved[2:5] == (124, 74, 68)
    assert saved[5:] == (
        "PRIVATE-TWO-490", "private vital from primary preview",
    )

    refreshed = client.get("/secondary/full/vitals")
    assert refreshed.status_code == 200
    assert "PRIVATE-TWO-490" in refreshed.text

    login(client, 3)
    third = client.get("/secondary/full/vitals")
    assert "PRIVATE-TWO-490" not in third.text
    response = client.post(
        "/secondary/full/vitals",
        data=vital_payload(third, "PRIVATE-THREE-490"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(private_rows(root, 2)) == 1
    assert len(private_rows(root, 3)) == 1
    assert private_rows(root, 3)[0][5] == "PRIVATE-THREE-490"


def test_csrf_cross_site_and_replay_are_denied(browser490):
    client, root = browser490
    assert client.post(
        "/secondary/full/vitals", data={"context": "anonymous"},
    ).status_code == 401

    login(client, 2)
    valid = vital_payload(client.get("/secondary/full/vitals"))
    assert client.post(
        "/secondary/full/vitals",
        data={**valid, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/full/vitals",
        data=valid, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert private_rows(root, 2) == []

    assert client.post(
        "/secondary/full/vitals",
        data=valid, follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/full/vitals", data=valid).status_code == 409
    assert client.post(
        "/secondary/full/vitals",
        data={**valid, "context": "altered-replay"},
    ).status_code == 409
    assert len(private_rows(root, 2)) == 1


def test_forged_identity_and_invalid_fields_are_rejected(browser490):
    client, root = browser490
    login(client, 2)
    valid = vital_payload(client.get("/secondary/full/vitals"))

    assert client.post(
        "/secondary/full/vitals?user_id=3", data=valid,
    ).status_code == 400

    for field, value in (
        ("user_id", "3"),
        ("database", "/opt/tracker/data/tracker.db"),
        ("sql", "DROP TABLE vital_readings"),
    ):
        assert client.post(
            "/secondary/full/vitals",
            data={**valid, field: value},
        ).status_code == 422

    for changes in (
        {"weight": "NaN"},
        {"systolic": "200", "diastolic": ""},
        {"pulse_bpm": "9"},
        {"measured_at": "not-a-date"},
    ):
        assert client.post(
            "/secondary/full/vitals",
            data={**valid, **changes},
        ).status_code == 422

    assert private_rows(root, 2) == []
    assert private_rows(root, 3) == []


def test_vitals_form_flags_and_production_fail_closed(browser490, monkeypatch):
    client, root = browser490
    login(client, 2)

    for key in (
        "TRACKER_FULLAPP_VITAL_WRITES490",
        "TRACKER_FULLAPP_WRITES488",
        "TRACKER_SECONDARY_VITAL_WRITES433",
    ):
        monkeypatch.setenv(key, "0")
        page = client.get("/secondary/full/vitals")
        assert page.status_code == 200
        assert 'action="/secondary/full/vitals"' not in page.text
        assert "form-action 'none'" in page.headers["content-security-policy"]
        assert client.post(
            "/secondary/full/vitals", data={"context": "disabled"},
        ).status_code == 404
        monkeypatch.setenv(key, "1")

    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post(
        "/secondary/full/vitals", data={"context": "disabled"},
    ).status_code == 404
    assert private_rows(root, 2) == []


def test_tampered_workspace_rejected_before_vital_write(browser490):
    client, root = browser490
    login(client, 2)
    valid = vital_payload(client.get("/secondary/full/vitals"))

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute(
            "UPDATE tracker_staged_workspace426 SET user_id=3"
        )

    assert client.post(
        "/secondary/full/vitals", data=valid,
    ).status_code == 401
    assert private_rows(root, 2) == []
    assert private_rows(root, 3) == []


def test_browser_middleware_contract_exact_vitals_path():
    from pathlib import Path
    main = Path("app/main.py").read_text()
    assert 'os.environ.get("TRACKER_FULLAPP_GATEWAY486", "0") == "1"' in main
    assert 'os.environ.get("TRACKER_FULLAPP_WRITES488", "0") == "1"' in main
    assert 'os.environ.get("TRACKER_FULLAPP_VITAL_WRITES490", "0") == "1"' in main
    assert "secondary_preview430.vital_writes_enabled433()" in main
    assert 'request.url.path == "/secondary/full/vitals"' in main
