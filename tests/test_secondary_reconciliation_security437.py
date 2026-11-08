"""Release 437 reconciliation security tests independently scheduled by loadfile."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest

from app import config
from app.worker_reconciliation437 import parse_request437, request_reconciliation437
from scripts.secondary_reconciliation437_support import browser, _login, _form, _db, _state

def test_account_switch_and_html_escaping_protect_private_audit(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = '<img src=x onerror="bad">'
    data["reason"] = '<script>alert("bad")</script> corrected vial tag'
    assert client.post(
        "/secondary/reconcile/correct", data=data,
        follow_redirects=False,
    ).status_code == 303

    detail2 = client.get("/secondary/reconcile/vials/2")
    assert detail2.status_code == 200
    assert '&lt;img' in detail2.text
    assert "<img src=x" not in detail2.text
    assert "&lt;script&gt;" in detail2.text
    assert '<script>' not in detail2.text

    _login(client, 3)
    detail3 = client.get("/secondary/reconcile/vials/2")
    assert detail3.status_code == 200
    assert "SEALED-3" in detail3.text
    assert "PRIVATE-ALPHA-437" not in detail3.text
    assert "CONCURRENT" not in detail3.text
    assert 'onerror="bad"' not in detail3.text
    assert "&lt;img" in detail3.text
    assert _state(root, 3)[1] == []


def test_forged_fields_invalid_values_and_csrf_are_rejected(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = "CORRECTION"

    for invalid in (
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DROP TABLE dose_logs"},
        {"content_value": "900"},
        {"volume_ml": "4"},
        {"status": "in_use"},
        {"reason": "short"},
        {"snapshot": "fake"},
        {"vial_id": "999"},
        {"vial_id": "invalid"},
    ):
        response = client.post(
            "/secondary/reconcile/correct", data={**data, **invalid},
        )
        assert response.status_code in (409, 422), (invalid, response.status_code)

    assert client.post(
        "/secondary/reconcile/correct", data={**data, "csrf_token": "bad"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconcile/correct", data=data,
        headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconcile/correct?user_id=3", data=data,
    ).status_code == 400
    assert client.get(
        "/secondary/reconcile?user_id=3",
    ).status_code == 400
    assert _state(root, 2)[1] == []
    assert _state(root, 3)[1] == []


def test_disabled_flag_keeps_reconciliation_read_only_and_prod_denied(browser, monkeypatch):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = "CORRECTION"
    monkeypatch.delenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", raising=False)

    report = client.get("/secondary/reconcile")
    assert report.status_code == 200
    detail = client.get("/secondary/reconcile/vials/2")
    assert detail.status_code == 200
    assert 'action="/secondary/reconcile/correct"' not in detail.text
    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 404
    assert _state(root, 2)[1] == []

    monkeypatch.setenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/reconcile").status_code == 404
    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 404


def test_unauthenticated_and_admin_worker_identity_are_denied(browser):
    client, root = browser
    assert client.get(
        "/secondary/reconcile", follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/reconcile/correct", data={},
    ).status_code == 401
    with pytest.raises(PermissionError):
        request_reconciliation437(1, "report", data_root=root)
    with pytest.raises(ValueError):
        request_reconciliation437(2, "query", data_root=root)
