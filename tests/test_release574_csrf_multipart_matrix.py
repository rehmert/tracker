"""Release 574: every registered multipart upload rejects unsigned writes.

All tests run with disposable pytest/Client data, never production uploads.
Only missing/forged CSRF tokens are submitted to the entire upload matrix;
no successful upload to an unknown endpoint is attempted.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/tracker_csrf_inventory572.py"


@pytest.fixture(scope="module")
def inventory574():
    spec = importlib.util.spec_from_file_location("csrf_upload574", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from app.main import app as tracker
    return module.build(tracker)


@pytest.fixture
def client574(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        page = client.get("/labs")
        assert page.status_code == 200
        token = client.cookies.get(COOKIE_NAME)
        assert token and token.startswith("v1.")
        yield client, token


def _sample_url(path):
    return re.sub(r"\{[^{}]+\}", "0", path)


def test_574_all_multipart_upload_routes_reject_missing_csrf(
    inventory574, client574,
):
    client, token = client574
    targets = inventory574["file_upload_writes"]
    assert len(targets) == 11, targets

    for method, route in targets:
        response = client.request(
            method, _sample_url(route),
            files={"csrf_probe": ("invalid.txt", b"QA", "text/plain")},
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            method, route, response.status_code,
            response.text[:120],
        )
        assert "CSRF token required" in response.text, (method, route)
    print(f"STRICT_MULTIPART_UPLOAD_ROUTE_DENIALS={len(targets)}")


def test_574_all_multipart_upload_routes_reject_forged_header(
    inventory574, client574,
):
    client, token = client574
    targets = inventory574["file_upload_writes"]
    assert len(targets) == 11, targets

    for method, route in targets:
        response = client.request(
            method, _sample_url(route),
            files={"csrf_probe": ("invalid.txt", b"QA", "text/plain")},
            headers={HEADER_NAME: token + "forged"},
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            method, route, response.status_code,
            response.text[:120],
        )
        assert "CSRF token required" in response.text, (method, route)


def test_574_signed_header_preserves_labs_csv_parser_compatibility(client574):
    client, token = client574
    # Existing Release 520 uses deliberately invalid CSV to prove that
    # valid signed headers preserve access to the real parser without a
    # successful user-data write.
    response = client.post(
        "/labs/import-csv",
        data={"drawn_on": "2026-11-11", "lab_name": "QA 574 invalid csv"},
        files={"csv_file": ("bad.csv", b"not,a,valid,csv\n", "text/csv")},
        headers={HEADER_NAME: token},
        follow_redirects=False,
    )
    assert response.status_code != 403
    assert response.headers.get("x-tracker-csrf-report") == "valid"
