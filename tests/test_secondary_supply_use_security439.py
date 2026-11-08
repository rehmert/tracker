"""Release 439 supply-use security tests independently scheduled by loadfile."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app import config
from app.worker_supply_use439 import parse_request439, request_use439
from scripts.secondary_supply_use439_support import browser, _login, _form, _state

def test_invalid_links_and_overdraw_cannot_mutate_stock(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)

    for invalid in (
        {"supply_id": "999"},
        {"supply_id": "not-an-id"},
        {"reference": "dose:999"},
        {"reference": "reconstitution:999"},
        {"reference": "admin:1"},
        {"reference": "dose:-1"},
        {"supply_id": "1", "reference": "dose:1"},
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "NaN"},
        {"amount": "6"},
        {"amount": "1.5"},
        {"supply_id": "1", "reference": "reconstitution:1", "amount": "4"},
        {"user_id": "3"},
        {"sql": "SELECT * FROM supplies"},
        {"database": "/opt/tracker/data/tracker.db"},
    ):
        reply = client.post("/secondary/supplies/use", data={**data, **invalid})
        assert reply.status_code == 422, (invalid, reply.status_code, reply.text[:100])
    assert _state(root, 2)[1] == []
    assert _state(root, 3)[1] == []


def test_accounts_have_independent_stock_and_escaped_labels(browser):
    client, root = browser
    _login(client, 2)
    assert client.post(
        "/secondary/supplies/use", data=_form(client),
        follow_redirects=False,
    ).status_code == 303

    _login(client, 3)
    page = client.get("/secondary/supplies/use")
    assert page.status_code == 200
    assert "PRIVATE-NEEDLE-3" in page.text
    assert "PRIVATE-NEEDLE-2" not in page.text
    assert "&lt;img" in page.text
    assert "<img src=x" not in page.text
    assert "Recent Supply Use" in page.text
    assert "No supply consumption recorded yet" in page.text

    own = _form(client, supply_id=2, reference="dose:1")
    assert client.post(
        "/secondary/supplies/use", data=own, follow_redirects=False,
    ).status_code == 303
    assert _state(root, 2)[0][1] == (2, 4.0)
    assert _state(root, 3)[0][1] == (2, 4.0)
    assert len(_state(root, 2)[1]) == len(_state(root, 3)[1]) == 1


def test_csrf_fetch_site_unauthenticated_and_flags(browser, monkeypatch):
    client, root = browser
    assert client.get(
        "/secondary/supplies/use", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies/use", data={}).status_code == 401
    _login(client, 2)
    form = _form(client)
    assert client.post(
        "/secondary/supplies/use",
        data={**form, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies/use",
        data=form, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies/use?user_id=3", data=form,
    ).status_code == 400

    monkeypatch.delenv("TRACKER_SECONDARY_SUPPLY_USE439", raising=False)
    assert client.get("/secondary/supplies/use").status_code == 404
    assert client.post("/secondary/supplies/use", data=form).status_code == 404
    assert client.get("/secondary/supplies").status_code == 200
    assert 'href="/secondary/supplies/use"' not in (
        client.get("/secondary/supplies").text
    )
    assert _state(root, 2)[1] == []
    monkeypatch.setenv("TRACKER_SECONDARY_SUPPLY_USE439", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/supplies/use").status_code == 404
    assert client.post("/secondary/supplies/use", data=form).status_code == 404


def test_parent_rejects_administrator_and_generic_operations(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_use439(1, "options", data_root=root)
    with pytest.raises(ValueError):
        request_use439(2, "sql", data_root=root)


def test_source_middleware_is_narrow_and_gated():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert 'secondary_preview430.supply_use_enabled439()' in source
    assert 'request.url.path == "/secondary/supplies/use"' in source
    assert "and not secondary_form_post433" in source
