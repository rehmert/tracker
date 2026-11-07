"""Release 491: authenticated dose, food and water forms in private preview."""

import re
import sqlite3
from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def browser491(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    for name in (
        "TRACKER_SECONDARY_PREVIEW430",
        "TRACKER_SECONDARY_DOSE_WRITES434",
        "TRACKER_SECONDARY_FOOD_WRITES456",
        "TRACKER_FULLAPP_GATEWAY486",
        "TRACKER_FULLAPP_WRITES488",
        "TRACKER_FULLAPP_DOSE_WRITES491",
        "TRACKER_FULLAPP_FOOD_WRITES491",
    ):
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    auth.bootstrap("admin491", "admin-test-password-491-secure")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}",
            f"secure-secondary-password-491-{uid}",
        )
        with sqlite3.connect(
            tmp_path / "users" / str(uid) / "tracker.db"
        ) as db:
            db.execute("""
                INSERT INTO compounds
                    (name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (f"compound-of-user-{uid}-491",))
            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,
                     content_value,content_unit,status,use_coa_content,
                     unit_price_cents,notes,storage_notes)
                VALUES (1, ?, '', '', '', 'lyophilized',
                        10, 'mg', 'sealed', 0, 0, '', '')
            """, (f"vial-for-{uid}-491",))

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def field491(html, name):
    found = re.search(
        rf'name="{re.escape(name)}"\s+value="([^"]+)"', html,
    )
    assert found, f"Missing hidden {name}"
    return found.group(1)


def form491(html, action):
    match = re.search(
        r'<form method="post" action="' + re.escape(action)
        + r'"[^>]*>(.*?)</form>', html, re.S,
    )
    assert match, f"Missing form for {action}"
    return match.group(1)


def login491(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secure-secondary-password-491-{uid}",
            "csrf_token": field491(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def dose_data491(page):
    source = form491(page.text, "/secondary/full/doses")
    return {
        "csrf_token": field491(source, "csrf_token"),
        "submission_token": field491(source, "submission_token"),
        "vial_id": "1",
        "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "amount": "2",
        "unit": "mg",
        "site": "Abdomen lower left",
        "notes": "private-dose-491",
    }


def water_data491(page):
    source = form491(page.text, "/secondary/full/food/water")
    return {
        "csrf_token": field491(source, "csrf_token"),
        "submission_token": field491(source, "submission_token"),
        "day": date.today().isoformat(),
        "ounces": "12.5",
    }


def food_data491(page):
    from app.secondary_nutrients463 import MACROS

    source = form491(page.text, "/secondary/full/food/entry")
    fields = {
        "csrf_token": field491(source, "csrf_token"),
        "submission_token": field491(source, "submission_token"),
        "day": date.today().isoformat(),
        "name": "private-test-yogurt-491",
        "meal": "Breakfast",
        "servings": "2",
    }
    fields.update({key: "" for key, _label, _unit in MACROS})
    fields.update({"energy": "100", "proteins": "15", "fat": "2"})
    return fields


def state491(root, uid):
    with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
        dose = db.execute("""
            SELECT entered_value,entered_unit,amount_base,kind
            FROM dose_logs ORDER BY id
        """).fetchall()
        vial = db.execute("""
            SELECT status FROM vials ORDER BY id
        """).fetchall()
        water = db.execute("""
            SELECT ounces FROM tracker_water_entries ORDER BY id
        """).fetchall()
        food = db.execute("""
            SELECT p.name,e.meal,e.servings
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            ORDER BY e.id
        """).fetchall()
    return dose, vial, water, food


def test_dose_private_write_and_readback_two_users(browser491):
    client, root = browser491
    login491(client, 2)
    page = client.get("/secondary/full/doses")
    assert page.status_code == 200, page.text[-400:]
    assert "vial-for-2-491" in page.text
    assert "vial-for-3-491" not in page.text
    assert "form-action 'self'" in page.headers["content-security-policy"]

    payload = dose_data491(page)
    done = client.post(
        "/secondary/full/doses", data=payload, follow_redirects=False,
    )
    assert done.status_code == 303, done.text[-400:]
    assert done.headers["location"] == "/secondary/full/doses"
    assert state491(root, 2)[0] == [(2.0, "mg", 2000.0, "dose")]
    assert state491(root, 2)[1] == [("in_use",)]
    assert state491(root, 3)[0] == []
    assert not (root / "tracker.db").exists()

    seen = client.get("/secondary/full/doses")
    assert seen.status_code == 200
    assert "compound-of-user-2-491" in seen.text

    login491(client, 3)
    other = client.get("/secondary/full/doses")
    assert "vial-for-3-491" in other.text
    assert "vial-for-2-491" not in other.text
    assert client.post(
        "/secondary/full/doses",
        data=dose_data491(other), follow_redirects=False,
    ).status_code == 303
    assert len(state491(root, 2)[0]) == len(state491(root, 3)[0]) == 1


def test_dose_csrf_replay_overdraw_and_forged_identity(browser491):
    client, root = browser491
    assert client.post("/secondary/full/doses").status_code == 401
    login491(client, 2)
    page = client.get("/secondary/full/doses")
    payload = dose_data491(page)

    assert client.post(
        "/secondary/full/doses", data={**payload, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/full/doses",
        data=payload, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/full/doses?user_id=3", data=payload,
    ).status_code == 400
    assert client.post(
        "/secondary/full/doses", data={**payload, "user_id": "3"},
    ).status_code == 422
    assert client.post(
        "/secondary/full/doses", data={**payload, "amount": "15"},
    ).status_code == 422
    assert state491(root, 2)[0] == []

    assert client.post(
        "/secondary/full/doses", data=payload, follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/full/doses", data=payload,
    ).status_code == 409
    assert len(state491(root, 2)[0]) == 1


def test_food_water_private_writes_and_readback_two_users(browser491):
    client, root = browser491
    login491(client, 2)
    page = client.get("/secondary/full/food")
    assert page.status_code == 200, page.text[-400:]
    assert "form-action 'self'" in page.headers["content-security-policy"]

    water = water_data491(page)
    food = food_data491(page)
    assert water["submission_token"] != food["submission_token"]

    first = client.post(
        "/secondary/full/food/water", data=water, follow_redirects=False,
    )
    assert first.status_code == 303, first.text[:700]
    assert first.headers["location"].endswith(date.today().isoformat())

    second = client.post(
        "/secondary/full/food/entry", data=food, follow_redirects=False,
    )
    assert second.status_code == 303, second.text[:700]

    assert state491(root, 2)[2] == [(12.5,)]
    assert state491(root, 2)[3] == [
        ("private-test-yogurt-491", "Breakfast", 2.0),
    ]
    assert state491(root, 3)[2:] == ([], [])
    assert not (root / "tracker.db").exists()
    day = client.get("/secondary/full/food?day=" + date.today().isoformat())
    assert day.status_code == 200
    assert "private-test-yogurt-491" in day.text

    login491(client, 3)
    other = client.get("/secondary/full/food")
    assert other.status_code == 200
    assert "private-test-yogurt-491" not in other.text
    assert client.post(
        "/secondary/full/food/water",
        data=water_data491(other), follow_redirects=False,
    ).status_code == 303
    assert state491(root, 3)[2] == [(12.5,)]
    assert state491(root, 2)[2] == [(12.5,)]


def test_food_and_water_csrf_replay_reject_extra(browser491):
    client, root = browser491
    assert client.post("/secondary/full/food/water").status_code == 401
    assert client.post("/secondary/full/food/entry").status_code == 401
    login491(client, 2)
    page = client.get("/secondary/full/food")
    water, food = water_data491(page), food_data491(page)

    for path, payload in (
        ("/secondary/full/food/water", water),
        ("/secondary/full/food/entry", food),
    ):
        assert client.post(
            path, data={**payload, "csrf_token": "forged"},
        ).status_code == 403
        assert client.post(
            path, data=payload, headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code == 403
        assert client.post(
            path + "?uid=3", data=payload,
        ).status_code == 400
        assert client.post(
            path, data={**payload, "database": "/tmp/admin.db"},
        ).status_code == 422

        assert client.post(
            path, data=payload, follow_redirects=False,
        ).status_code == 303
        assert client.post(path, data=payload).status_code == 409

    assert len(state491(root, 2)[2]) == 1
    assert len(state491(root, 2)[3]) == 1
    assert state491(root, 3)[2:] == ([], [])


def test_write_flags_fail_closed_without_new_worker_spawning(
    browser491, monkeypatch,
):
    client, root = browser491
    login491(client, 2)
    for gate, page_path, post_path in (
        ("TRACKER_FULLAPP_DOSE_WRITES491", "/secondary/full/doses",
         "/secondary/full/doses"),
        ("TRACKER_SECONDARY_DOSE_WRITES434", "/secondary/full/doses",
         "/secondary/full/doses"),
        ("TRACKER_FULLAPP_FOOD_WRITES491", "/secondary/full/food",
         "/secondary/full/food/water"),
        ("TRACKER_SECONDARY_FOOD_WRITES456", "/secondary/full/food",
         "/secondary/full/food/entry"),
    ):
        monkeypatch.setenv(gate, "0")
        page = client.get(page_path)
        assert page.status_code == 200
        assert 'action="' + post_path + '"' not in page.text
        assert client.post(post_path, data={"uid": "3"}).status_code == 404
        monkeypatch.setenv(gate, "1")

    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post("/secondary/full/doses").status_code == 404
    assert client.post("/secondary/full/food/water").status_code == 404
    assert client.post("/secondary/full/food/entry").status_code == 404
    assert state491(root, 2)[0] == []


def test_tampered_workspace_and_admin_source_unavailable(browser491):
    client, root = browser491
    login491(client, 2)
    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute("UPDATE tracker_staged_workspace426 SET user_id=3")
    assert client.post("/secondary/full/doses").status_code == 401
    assert client.post("/secondary/full/food/entry").status_code == 401
    assert not (root / "tracker.db").exists()


def test_main_middleware_scopes_new_paths_and_flags():
    from pathlib import Path
    main = Path("app/main.py").read_text()
    assert 'os.environ.get("TRACKER_FULLAPP_DOSE_WRITES491", "0") == "1"' in main
    assert 'os.environ.get("TRACKER_FULLAPP_FOOD_WRITES491", "0") == "1"' in main
    assert "secondary_preview430.dose_writes_enabled434()" in main
    assert "secondary_preview430.food_writes_enabled456()" in main
    assert 'request.url.path == "/secondary/full/doses"' in main
    assert '"/secondary/full/food/water"' in main
    assert '"/secondary/full/food/entry"' in main
