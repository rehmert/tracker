"""Release 435: isolated secondary compounds/vials create-only workflow."""

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.worker_inventory435 import (
    parse_request435, request_inventory435, validate_inventory435,
)
from app.worker_dose_write434 import request_dose434


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_DOSE_WRITES434", "1")

    auth.bootstrap("operator", "administrator-secure-password-435")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-435",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _input(html, key):
    match = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"', html,
    )
    assert match is not None, f"Expected hidden input: {key}"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-435",
            "csrf_token": _input(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def _form(client, action):
    page = client.get("/secondary/inventory")
    assert page.status_code == 200
    assert f'action="/secondary/inventory/{action}"' in page.text
    fragment = page.text.split(
        f'<form method="post" action="/secondary/inventory/{action}"',
        1,
    )[1].split("</form>", 1)[0]
    return {
        "csrf_token": _input(fragment, "csrf_token"),
        "submission_token": _input(fragment, "submission_token"),
    }


def _compound_form(client, name="PRIVATE-COMPOUND-435", unit="mg"):
    return {
        **_form(client, "compounds"),
        "name": name,
        "category": "peptide",
        "primary_unit": unit,
        "notes": "PRIVATE-COMPOUND-NOTES",
    }


def _vial_form(client, cid=1, value="10", unit="mg"):
    return {
        **_form(client, "vials"),
        "compound_id": str(cid),
        "label": "PRIVATE-VIAL-435",
        "content_value": value,
        "content_unit": unit,
        "form": "lyophilized",
        "volume_ml": "",
        "lot": "LOT-435",
        "cap_color": "Blue",
        "notes": "PRIVATE-VIAL-NOTES",
    }


def _dbstate(root, uid):
    with sqlite3.connect(
        root / "users" / str(uid) / "tracker.db",
    ) as db:
        compounds = db.execute("""
            SELECT id,name,category,primary_unit
            FROM compounds ORDER BY id
        """).fetchall()
        vials = db.execute("""
            SELECT id,compound_id,label,content_value,
                   content_unit,status,form,volume_ml
            FROM vials ORDER BY id
        """).fetchall()
        tokens = db.execute("""
            SELECT operation,COUNT(*)
            FROM inventory_submissions
            WHERE operation LIKE 'secondary_create_%435'
            GROUP BY operation ORDER BY operation
        """).fetchall()
    return compounds, vials, tokens


def _create_compound(client, name="PRIVATE-COMPOUND-435", unit="mg"):
    response = client.post(
        "/secondary/inventory/compounds",
        data=_compound_form(client, name, unit),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:300]
    assert response.headers["location"] == "/secondary/inventory"
    return response


def test_compound_and_vial_created_in_only_one_private_workspace(browser):
    client, root = browser
    _login(client, 2)
    _create_compound(client)

    compounds, vials, tokens = _dbstate(root, 2)
    assert compounds == [(1, "PRIVATE-COMPOUND-435", "peptide", "mg")]
    assert not vials
    assert ("secondary_create_compound435", 1) in tokens
    assert _dbstate(root, 3)[0] == []
    assert not (root / "tracker.db").exists()

    response = client.post(
        "/secondary/inventory/vials",
        data=_vial_form(client),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:200]

    compounds, vials, tokens = _dbstate(root, 2)
    assert vials == [
        (1, 1, "PRIVATE-VIAL-435", 10.0, "mg", "sealed", "lyophilized", None)
    ]
    assert ("secondary_create_vial435", 1) in tokens
    assert _dbstate(root, 3)[1] == []

    page = client.get("/secondary/inventory")
    assert page.status_code == 200
    assert "PRIVATE-COMPOUND-435" in page.text
    assert "PRIVATE-VIAL-435" in page.text
    assert 'href="/secondary/inventory"' in client.get("/secondary/overview").text


def test_newly_created_vial_can_be_used_by_existing_private_dose_worker(browser):
    client, root = browser
    _login(client, 2)
    _create_compound(client)
    assert client.post(
        "/secondary/inventory/vials", data=_vial_form(client),
        follow_redirects=False,
    ).status_code == 303

    report = request_dose434(
        2, "create_dose", {
            "vial_id": 1,
            "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "amount": 3.0,
            "unit": "mg",
            "site": "",
            "notes": "",
            "submission_token": str(uuid4()),
        }, root,
    )
    assert report["status"] == "created"
    state = _dbstate(root, 2)
    assert state[1][0][5] == "in_use"
    assert _dbstate(root, 3)[1] == []

    options = request_dose434(2, "options", data_root=root)
    assert options["items"][0]["remaining_base"] == 7000


def test_repeat_token_and_duplicate_casefold_name_do_not_create_extra_records(browser):
    client, root = browser
    _login(client, 2)
    form = _compound_form(client)
    assert client.post(
        "/secondary/inventory/compounds", data=form,
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/inventory/compounds", data=form,
    ).status_code == 409
    assert client.post(
        "/secondary/inventory/compounds",
        data={**form, "name": "CHANGED-WITH-SAME-TOKEN"},
    ).status_code == 409

    fresh = _compound_form(client, "private-compound-435")
    assert client.post(
        "/secondary/inventory/compounds", data=fresh,
    ).status_code == 422

    assert len(_dbstate(root, 2)[0]) == 1


def test_replayed_vial_token_and_concurrent_creates_are_idempotent(browser):
    client, root = browser
    _login(client, 2)
    _create_compound(client)
    data = _vial_form(client)
    assert client.post(
        "/secondary/inventory/vials", data=data,
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/inventory/vials", data=data,
    ).status_code == 409
    assert len(_dbstate(root, 2)[1]) == 1

    payload = {
        "compound_id": 1,
        "label": "CONCURRENT",
        "content_value": 5.0,
        "content_unit": "mg",
        "form": "lyophilized",
        "volume_ml": None,
        "lot": "",
        "cap_color": "",
        "notes": "",
        "submission_token": str(uuid4()),
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                request_inventory435, 2, "create_vial", payload, root,
            )
            for _ in range(2)
        ]
        results = [f.result() for f in futures]

    assert sorted(x["status"] for x in results) == ["created", "duplicate"]
    assert len(_dbstate(root, 2)[1]) == 2


def test_other_user_cannot_reference_foreign_compound_or_read_private_data(browser):
    client, root = browser
    _login(client, 2)
    _create_compound(client, "PRIVATE-SECOND")
    _login(client, 3)

    page = client.get("/secondary/inventory")
    assert page.status_code == 200
    assert "PRIVATE-SECOND" not in page.text
    assert "No compounds yet" in page.text

    response = client.post(
        "/secondary/inventory/vials",
        data=_vial_form(client, cid=1),
    )
    assert response.status_code == 422
    assert len(_dbstate(root, 2)[0]) == 1
    assert _dbstate(root, 2)[1] == []
    assert _dbstate(root, 3)[1] == []

    _create_compound(client, "<img src=x onerror=alert(1)>")
    other = client.get("/secondary/inventory").text
    assert "&lt;img" in other
    assert "<img src=x" not in other
    assert "PRIVATE-SECOND" not in other


def test_incompatible_units_and_invalid_vials_fail_closed(browser):
    client, root = browser
    _login(client, 2)
    _create_compound(client, "Somatropin", "IU")

    original = _vial_form(client, unit="IU")
    bad_forms = (
        {"content_unit": "mg"},
        {"content_value": "0"},
        {"content_value": "-1"},
        {"content_value": "NaN"},
        {"content_value": "1000001"},
        {"content_unit": "wrong"},
        {"compound_id": "3"},
        {"form": "unknown"},
        {"form": "solution", "volume_ml": ""},
        {"form": "lyophilized", "volume_ml": "2"},
        {"content_value": "10", "volume_ml": "inf"},
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DELETE FROM compounds"},
    )
    for change in bad_forms:
        reply = client.post(
            "/secondary/inventory/vials", data={**original, **change},
        )
        assert reply.status_code == 422, (change, reply.status_code, reply.text[:100])

    assert not _dbstate(root, 2)[1]
    assert not _dbstate(root, 3)[1]


def test_solution_volume_and_primary_unit_rules(browser):
    client, root = browser
    _login(client, 2)
    invalid = _compound_form(client, name="Somatropin", unit="mg")
    assert client.post(
        "/secondary/inventory/compounds", data=invalid,
    ).status_code == 422

    _create_compound(client, "Somatropin", "IU")
    form = _vial_form(client, unit="IU")
    form.update({"form": "solution", "volume_ml": "3.5"})
    assert client.post(
        "/secondary/inventory/vials", data=form,
        follow_redirects=False,
    ).status_code == 303
    assert _dbstate(root, 2)[1][0][-2:] == ("solution", 3.5)


def test_csrf_cross_site_and_unauthenticated_cannot_write(browser):
    client, root = browser
    assert client.get(
        "/secondary/inventory", follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/inventory/compounds", data={},
    ).status_code == 401

    _login(client, 2)
    form = _compound_form(client)
    assert client.post(
        "/secondary/inventory/compounds",
        data={**form, "csrf_token": "bad"},
    ).status_code == 403
    assert client.post(
        "/secondary/inventory/compounds",
        data=form, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/inventory/compounds?user_id=3", data=form,
    ).status_code == 400
    assert client.get(
        "/secondary/inventory?database=/tmp/other.db",
    ).status_code == 400
    assert not _dbstate(root, 2)[0]


def test_disable_write_flag_keeps_inventory_read_only(browser, monkeypatch):
    client, root = browser
    _login(client, 2)
    _create_compound(client)
    form = _vial_form(client)

    monkeypatch.delenv("TRACKER_SECONDARY_INVENTORY_WRITES435", raising=False)
    page = client.get("/secondary/inventory")
    assert page.status_code == 200
    assert "PRIVATE-COMPOUND-435" in page.text
    assert 'action="/secondary/inventory/vials"' not in page.text
    assert client.post(
        "/secondary/inventory/vials", data=form,
    ).status_code == 404
    assert not _dbstate(root, 2)[1]

    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/inventory").status_code == 404
    assert client.post(
        "/secondary/inventory/vials", data=form,
    ).status_code == 404


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"inventory","user_id":3}',
    b'{"action":"create_vial","sql":"DROP TABLE vials","payload":{}}',
    b'{"action":"create_compound","payload":{"database":"/root"}}',
    b'{"action":"inventory","action":"inventory"}',
    b"x" * 4097,
))
def test_worker_payload_is_strict_and_bounded(raw):
    with pytest.raises(ValueError):
        parse_request435(raw)


def test_parent_rejects_admin_identity_and_generic_sql(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_inventory435(1, "inventory", data_root=root)
    with pytest.raises(ValueError):
        request_inventory435(2, "sql", data_root=root)
    assert request_inventory435(2, "inventory", data_root=root)["compounds"] == []


def test_middleware_only_exempts_gated_private_inventory_forms():
    from pathlib import Path
    s = Path("app/main.py").read_text()
    assert 'secondary_preview430.inventory_writes_enabled435()' in s
    assert '"/secondary/inventory/compounds"' in s
    assert '"/secondary/inventory/vials"' in s
    assert "and not secondary_form_post433" in s
