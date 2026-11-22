"""Release 747: actual signed CRUD acceptance in disposable Tracker, HTTP/HTTPS.

Tests REAL application router and middleware, persisted synthetic records and
signed, missing and forged writes. No installed app, external network or
production data. Real-phone and cross-account acceptance remains separate.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.main import app


@pytest.fixture
def strict_app747(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    yield


def get_token(client, path):
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code)
    token = client.cookies.get(COOKIE_NAME)
    assert token and token.startswith("v1.")
    return token


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_747_notes_complete_signed_create_edit_delete_and_history(strict_app747, scheme):
    with TestClient(app, base_url=f"{scheme}://testserver") as client:
        token = get_token(client, "/pages/new")
        values = {"title": "747 synthetic note", "body": "first private text", "tags": "qa"}
        missing = client.post("/pages", data=values, follow_redirects=False)
        assert missing.status_code == 403
        created = client.post("/pages", data={**values, "csrf_token": token},
                              follow_redirects=False)
        assert created.status_code == 303
        match = re.search(r"/pages/(\d+)", created.headers["location"])
        assert match, created.headers["location"]
        item = f"/pages/{match.group(1)}"
        assert "first private text" in client.get(item).text

        bad = client.post(item, data={**values, "body": "forged rewrite",
                                      "csrf_token": "forged-747"},
                          follow_redirects=False)
        assert bad.status_code == 403
        assert "forged rewrite" not in client.get(item).text
        updated = client.post(item, data={**values, "body": "second private text",
                                          "csrf_token": token},
                              follow_redirects=False)
        assert updated.status_code == 303
        assert "second private text" in client.get(item).text
        assert "first private text" in client.get(item + "/history").text

        unsigned_delete = client.post(item + "/delete", follow_redirects=False)
        assert unsigned_delete.status_code == 403
        assert client.get(item).status_code == 200
        deleted = client.post(item + "/delete", data={"csrf_token": token},
                              follow_redirects=False)
        assert deleted.status_code == 303
        assert client.get(item).status_code == 404


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_747_workout_equipment_signed_add_and_forged_denial(strict_app747, scheme):
    with TestClient(app, base_url=f"{scheme}://testserver") as client:
        token = get_token(client, "/workouts")
        name = "747 synthetic Nautilus"
        data = {"name": name, "kind": "selectorized",
                "gym": "Disposable QA gym", "manufacturer": "QA"}
        assert client.post("/workouts/equipment", data=data,
                           follow_redirects=False).status_code == 403
        assert client.post("/workouts/equipment",
                           data={**data, "csrf_token": "forged-747"},
                           follow_redirects=False).status_code == 403
        success = client.post("/workouts/equipment",
                              data={**data, "csrf_token": token},
                              follow_redirects=False)
        assert success.status_code == 303
        assert "err=" not in success.headers["location"]
        assert name in client.get("/workouts").text


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_747_regimen_signed_add_and_unsigned_delete_denied(strict_app747, scheme):
    with TestClient(app, base_url=f"{scheme}://testserver") as client:
        token = get_token(client, "/regimen")
        values = {"kind": "supplement", "name": "747 synthetic supplement",
                  "strength": "10 mg", "form": "Capsule"}
        assert client.post("/regimen/items", data=values,
                           follow_redirects=False).status_code == 403
        created = client.post("/regimen/items",
                              data={**values, "csrf_token": token},
                              follow_redirects=False)
        assert created.status_code == 303
        assert "err=" not in created.headers["location"]
        assert values["name"] in client.get("/regimen").text


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_747_foreign_origin_signed_writes_still_fail(strict_app747, scheme):
    with TestClient(app, base_url=f"{scheme}://testserver") as client:
        token = get_token(client, "/pages/new")
        resp = client.post("/pages", data={
            "title": "cross-site must not persist", "body": "synthetic",
            "csrf_token": token,
        }, headers={"Origin": "https://attacker.example",
                    "Sec-Fetch-Site": "cross-site"},
            follow_redirects=False)
        assert resp.status_code == 403
        assert "cross-site must not persist" not in client.get("/pages").text
