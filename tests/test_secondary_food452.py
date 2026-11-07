"""Release 452: isolated secondary food and water history acceptance tests.

Self-contained test fixture: two disabled private users, separate databases,
and a real DEV-only HTTPS preview mounted on a test ASGI application.
"""
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
from app.user_accounts427 import (
    stage_secondary_account427,
)
from app.user_bootstrap426 import initialize_staged_workspace426
from app.worker_food452 import (
    parse_request452, read_food_day452, validate_day452,
)
from app.worker_scope428 import SOURCE_ROOT, worker_environment428


DAY = "2026-11-06"


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    auth.bootstrap("operator", "administrator-sample-pass-452")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-pass-{uid}-452"
        )
        dbpath = tmp_path / "users" / str(uid) / "tracker.db"
        with sqlite3.connect(dbpath) as db:
            name = '<img src=x onerror="alert(1)"> USER-TWO' if uid == 2 else "USER-THREE"
            nutrients = json.dumps({
                "energy": float(uid * 75),
                "proteins": float(uid * 10),
                "carbohydrates": 12.0 if uid == 2 else None,
                "fat": 4.0,
                "fiber": None,
            })
            db.execute("""
                INSERT INTO tracker_food_products
                (name,serving_description,nutrients,source)
                VALUES (?, '1 serving', ?, 'manual')
            """, (name, nutrients))
            db.execute("""
                INSERT INTO tracker_food_entries
                (product_id,eaten_on,meal,servings)
                VALUES (1,?, 'Breakfast', 2)
            """, (DAY,))
            db.execute("""
                INSERT INTO tracker_water_entries
                (logged_on,ounces) VALUES (?,?)
            """, (DAY, 32 if uid == 2 else 12))
            db.commit()

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def login(browser, uid):
    form = browser.get("/secondary/login")
    assert form.status_code == 200
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', form.text)
    assert m
    response = browser.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-pass-{uid}-452",
            "csrf_token": m.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_private_food_day_separates_both_users_and_escapes_content(browser):
    client, root = browser
    login(client, 2)
    user2 = client.get("/secondary/food?day=" + DAY)
    assert user2.status_code == 200
    assert user2.headers["cache-control"] == "no-store"
    assert "Food &amp; Water" in user2.text
    assert "USER-TWO" in user2.text
    assert "USER-THREE" not in user2.text
    assert "&lt;img" in user2.text
    assert '<img src=x onerror=' not in user2.text
    assert "300.0 kcal" in user2.text
    assert "40.0 g" in user2.text
    assert "32.0 fl oz" in user2.text
    assert str(root) not in user2.text

    overview = client.get("/secondary/overview")
    assert 'href="/secondary/food"' in overview.text

    login(client, 3)
    user3 = client.get("/secondary/food?day=" + DAY)
    assert user3.status_code == 200
    assert "USER-THREE" in user3.text
    assert "USER-TWO" not in user3.text
    assert "450.0 kcal" in user3.text
    assert "12.0 fl oz" in user3.text


def test_only_authorized_day_is_accepted_no_sql_paths_or_user_id(browser):
    client, root = browser
    login(client, 2)

    assert client.get("/secondary/food?day=" + DAY).status_code == 200
    assert client.get("/secondary/food").status_code == 200
    for path in (
        "/secondary/food?user_id=3",
        "/secondary/food?database=/tmp/other.db",
        "/secondary/food?sql=SELECT",
        "/secondary/food?day=2026-11-06&day=2026-11-07",
    ):
        assert client.get(path).status_code == 400

    for day in ("tomorrow", "2026-02-30", "2026-1-6", "../private"):
        assert client.get("/secondary/food?day=" + day).status_code == 422

    assert client.post("/secondary/food").status_code == 405


def test_unauthenticated_prod_and_lockdown_cannot_view_food(browser, monkeypatch):
    client, root = browser
    before = client.get(
        "/secondary/food?day=" + DAY, follow_redirects=False
    )
    assert before.status_code == 303
    assert before.headers["location"] == "/secondary/login"

    login(client, 2)
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert client.get("/secondary/food?day=" + DAY).status_code == 404

    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/food?day=" + DAY).status_code == 404


@pytest.mark.parametrize("raw", [
    b"", b"[]", b'{"action":"food_day","day":"invalid"}',
    b'{"action":"food_day","day":"2026-11-06","user_id":3}',
    b'{"action":"food_day","day":"2026-11-06","sql":"SELECT"}',
    b'{"action":"food_day","day":"2026-11-06","day":"2026-11-07"}',
    b'{"action":"all","day":"2026-11-06"}',
    b"z" * 200,
])
def test_rejects_unallowlisted_or_duplicate_worker_requests(raw):
    with pytest.raises(ValueError):
        parse_request452(raw)


def test_parent_worker_returns_only_private_data_and_bounded_fields(browser):
    _, root = browser
    report2 = read_food_day452(2, DAY, root)
    report3 = read_food_day452(3, DAY, root)
    assert report2["user_id"] == 2
    assert report3["user_id"] == 3
    assert len(report2["items"]) == len(report3["items"]) == 1
    assert "USER-TWO" in report2["items"][0]["name"]
    assert report3["items"][0]["name"] == "USER-THREE"
    assert report2["totals"]["energy"] == 300
    assert report2["totals"]["proteins"] == 40
    assert report2["coverage"]["fiber"] == 0
    assert report2["items"][0]["fiber"] is None
    assert report3["water_oz"] == 12
    assert report2["http_listener_started"] is False
    assert report2["login_enabled"] is False
    with pytest.raises(PermissionError):
        read_food_day452(1, DAY, root)


def test_worker_rejects_foreign_workspace_directory(browser):
    _, root = browser
    env = worker_environment428(2, root)
    env["TRACKER_DATA_DIR"] = str(root / "users" / "3")
    result = subprocess.run(
        [sys.executable, "-m", "app.worker_food452"],
        input=json.dumps({"action": "food_day", "day": DAY}),
        env=env, cwd=SOURCE_ROOT,
        text=True, capture_output=True, timeout=45,
    )
    assert result.returncode != 0
    assert not result.stdout.strip()


def test_workspace_identity_tamper_rejected(browser):
    client, root = browser
    login(client, 2)
    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute("UPDATE tracker_staged_workspace426 SET user_id=3")
    response = client.get(
        "/secondary/food?day=" + DAY, follow_redirects=False
    )
    assert response.status_code == 303


def test_date_validator_normalizes_nothing():
    assert validate_day452(DAY) == DAY
    for raw in ("2026-1-06", "2026-13-06", None, 20261106, "2026-11-06 "):
        with pytest.raises(ValueError):
            validate_day452(raw)


# Release 453 weekly read-only acceptance.
def test_week453_private_isolation_and_navigation(browser):
    client, _ = browser
    login(client, 2)

    day = client.get("/secondary/food?day=" + DAY)
    assert 'href="/secondary/food/week?day=' in day.text

    week = client.get("/secondary/food/week?day=" + DAY)
    assert week.status_code == 200
    assert week.headers["cache-control"] == "no-store"
    assert "Weekly Nutrition" in week.text
    assert "300.0 kcal" in week.text
    assert "40.0 g" in week.text
    assert "32.0 fl oz" in week.text
    assert "USER-THREE" not in week.text
    assert "2026-10-31" in week.text

    login(client, 3)
    other = client.get("/secondary/food/week?day=" + DAY)
    assert other.status_code == 200
    assert "450.0 kcal" in other.text
    assert "12.0 fl oz" in other.text
    assert "300.0 kcal" not in other.text


def test_week453_rejects_untrusted_parameters(browser):
    client, _ = browser
    login(client, 2)
    for suffix in (
        "?user_id=3",
        "?database=/tmp/private.db",
        "?sql=SELECT",
        "?day=2026-11-06&day=2026-11-07",
    ):
        assert client.get("/secondary/food/week" + suffix).status_code == 400

    for invalid in ("bad", "2026-02-30", "0001-01-01"):
        assert client.get(
            "/secondary/food/week?day=" + invalid
        ).status_code == 422

    assert client.post("/secondary/food/week").status_code == 405


def test_week453_lockdown_and_prod_denial(browser, monkeypatch):
    client, _ = browser
    assert client.get(
        "/secondary/food/week", follow_redirects=False
    ).status_code == 303

    login(client, 2)
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert client.get("/secondary/food/week").status_code == 404

    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/food/week").status_code == 404
