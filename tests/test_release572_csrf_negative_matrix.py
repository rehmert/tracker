"""Release 572: exercise strict CSRF denial across every root write route.

A disposable TestClient and test database only. Session-signed and mounted
secondary writes are intentionally excluded: they have separate CSRF systems
and existing dedicated tests. No live setting is changed.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME

from test_release572_csrf_inventory import audit as audit_fixture


@pytest.fixture
def strict_client572(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    with TestClient(app) as client:
        yield client


def _sample_path(path):
    return re.sub(r"\{[^}]+\}", "0", path)


def test_all_registered_root_writes_reject_missing_csrf(strict_client572,
                                                         audit_fixture):
    route_data = audit_fixture.registered_writes(app)
    target = [row for row in route_data
              if not row["mounted"]
              and not row["signed_session_exception"]]
    assert len(target) > 100
    tested = set()
    for row in target:
        key = (row["method"], row["path"])
        if key in tested:
            continue
        tested.add(key)
        response = strict_client572.request(
            row["method"], _sample_path(row["path"]),
            content=b"{}",
            headers={"Content-Type": "application/json"},
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            key, response.status_code, response.text[:200],
        )
        assert "CSRF token required" in response.text, key
    print(f"STRICT_CSRF_REGISTERED_ROUTE_NEGATIVES={len(tested)}")


@pytest.mark.parametrize("path", [
    "/compounds", "/pk/compounds", "/labs/import-csv", "/coas/new",
])
def test_representative_writes_reject_invalid_double_submit_token(
    strict_client572, path,
):
    client = strict_client572
    page = client.get("/compounds")
    assert page.status_code == 200
    assert client.cookies.get(COOKIE_NAME)
    response = client.post(
        path, content=b"{}",
        headers={"Content-Type": "application/json",
                 HEADER_NAME: "forged-nonmatching-token"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert "CSRF token required" in response.text


def test_valid_cookie_header_cannot_bypass_foreign_origin(strict_client572):
    client = strict_client572
    page = client.get("/compounds")
    assert page.status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    assert token
    denied = client.post(
        "/pk/compounds", json={},
        headers={HEADER_NAME: token, "Origin": "https://attacker.example"},
        follow_redirects=False,
    )
    assert denied.status_code == 403
    assert "Cross-origin" in denied.text
