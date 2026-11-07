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


# Release 454 single-worker weekly acceptance

from app.worker_week454 import (
    days454,
    parse_request454,
    read_food_week454,
    validate_response454,
)

def test_week_has_exactly_seven_days():
    days = days454(DAY)
    assert days[0] == "2026-10-31"
    assert days[-1] == DAY
    assert len(days) == len(set(days)) == 7


@pytest.mark.parametrize("raw", [
    b"",
    b"[]",
    b'{"action":"food_week","day":"bad"}',
    b'{"action":"food_week","day":"0001-01-01"}',
    b'{"action":"food_week","day":"2026-11-06","user_id":3}',
    b'{"action":"food_week","day":"2026-11-06","sql":"SELECT"}',
    b'{"action":"food_week","day":"2026-11-06","day":"2026-11-07"}',
    b'{"action":"food_day","day":"2026-11-06"}',
    b"z" * 200,
])
def test_worker_request_allowlist(raw):
    with pytest.raises(ValueError):
        parse_request454(raw)


def test_weekly_worker_isolates_two_users(browser):
    _, root = browser

    first = read_food_week454(2, DAY, root)
    second = read_food_week454(3, DAY, root)

    assert len(first) == len(second) == 7
    assert first[-1]["totals"]["energy"] == 300
    assert first[-1]["water_oz"] == 32
    assert second[-1]["totals"]["energy"] == 450
    assert second[-1]["water_oz"] == 12

    with pytest.raises(PermissionError):
        read_food_week454(1, DAY, root)


def test_weekly_response_rejects_foreign_identity(browser):
    _, root = browser
    reports = read_food_week454(2, DAY, root)

    payload = {
        "mode": "offline-food-week454",
        "user_id": 2,
        "end_day": DAY,
        "reports": reports,
    }

    payload["reports"][0]["user_id"] = 3

    with pytest.raises(RuntimeError):
        validate_response454(payload, 2, DAY)


def test_weekly_worker_rejects_foreign_directory(browser):
    _, root = browser

    env = worker_environment428(2, root)
    env["TRACKER_DATA_DIR"] = str(root / "users" / "3")

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_week454"],
        input=json.dumps({
            "action": "food_week",
            "day": DAY,
        }),
        env=env,
        cwd=SOURCE_ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode != 0
    assert not result.stdout.strip()


def test_browser_week_still_works(browser):
    client, _ = browser
    login(client, 2)

    response = client.get("/secondary/food/week?day=" + DAY)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "300.0 kcal" in response.text
    assert "32.0 fl oz" in response.text

    assert client.post("/secondary/food/week").status_code == 405


# Release 455: authenticated, isolated weekly nutrition CSV.
def test_week_csv455_private_export(browser):
    import csv
    import io

    client, root = browser
    login(client, 2)

    page = client.get("/secondary/food/week?day=" + DAY)
    assert page.status_code == 200
    assert (
        '/secondary/food/week.csv?day=' + DAY
    ) in page.text

    response = client.get(
        "/secondary/food/week.csv?day=" + DAY
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "text/csv" in response.headers["content-type"]
    assert "attachment;" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 7
    assert rows[0]["date"] == "2026-10-31"
    assert rows[-1]["date"] == DAY
    assert float(rows[-1]["calories_kcal"]) == 300
    assert float(rows[-1]["protein_g"]) == 40
    assert float(rows[-1]["water_fl_oz"]) == 32
    assert rows[-1]["fiber_g"] == ""
    assert rows[-1]["fiber_coverage"] == "0"
    assert rows[-1]["has_more_entries"] == "no"
    assert "USER-THREE" not in response.text
    assert str(root) not in response.text

    login(client, 3)

    other = client.get(
        "/secondary/food/week.csv?day=" + DAY
    )
    assert other.status_code == 200

    other_rows = list(
        csv.DictReader(io.StringIO(other.text))
    )

    assert float(other_rows[-1]["calories_kcal"]) == 450
    assert float(other_rows[-1]["water_fl_oz"]) == 12
    assert float(other_rows[-1]["protein_g"]) == 60
    assert "300.0" not in other.text


def test_week_csv455_rejects_query_injection(browser):
    client, _ = browser
    login(client, 2)

    for suffix in (
        "?user_id=3",
        "?database=/tmp/private.db",
        "?sql=SELECT",
        "?day=2026-11-06&day=2026-11-07",
    ):
        assert client.get(
            "/secondary/food/week.csv" + suffix
        ).status_code == 400

    for invalid in (
        "not-a-date",
        "2026-02-30",
        "0001-01-01",
    ):
        assert client.get(
            "/secondary/food/week.csv?day=" + invalid
        ).status_code == 422

    assert client.post(
        "/secondary/food/week.csv"
    ).status_code == 405


def test_week_csv455_prod_and_lockdown(browser, monkeypatch):
    client, _ = browser

    response = client.get(
        "/secondary/food/week.csv",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/secondary/login"

    login(client, 2)

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )

    assert client.get(
        "/secondary/food/week.csv"
    ).status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )

    assert client.get(
        "/secondary/food/week.csv"
    ).status_code == 404


def test_week_csv455_missing_values_and_partial():
    import csv
    import io

    from app.secondary_week_csv455 import (
        render_week_csv455,
    )
    from app.worker_week454 import days454

    reports = []

    for day in days454(DAY):
        reports.append({
            "day": day,
            "items": [],
            "totals": {
                key: 0.0 for key in (
                    "energy", "proteins",
                    "carbohydrates", "fat", "fiber"
                )
            },
            "coverage": {
                key: 0 for key in (
                    "energy", "proteins",
                    "carbohydrates", "fat", "fiber"
                )
            },
            "water_oz": 0.0,
            "water_target_oz": 140.0,
            "has_more": False,
        })

    reports[-1]["has_more"] = True
    reports[-1]["coverage"]["energy"] = 1
    reports[-1]["totals"]["energy"] = 125.0

    text = render_week_csv455(reports, DAY)
    rows = list(csv.DictReader(io.StringIO(text)))

    assert len(rows) == 7
    assert rows[0]["calories_kcal"] == ""
    assert rows[0]["water_fl_oz"] == "0.0"
    assert rows[-1]["calories_kcal"] == "125.0"
    assert rows[-1]["has_more_entries"] == "yes"
    assert rows[-1]["protein_g"] == ""


# Release 455 correction: CSV coverage names match exact headers.
def test_week_csv455_coverage_columns_match_headers():
    import csv
    import io

    from app.secondary_week_csv455 import (
        FIELDS,
        COVERAGE_COLUMN,
        render_week_csv455,
    )
    from app.worker_week454 import days454

    assert set(COVERAGE_COLUMN.values()).issubset(set(FIELDS))

    reports = []

    for day in days454(DAY):
        reports.append({
            "day": day,
            "items": [{}],
            "totals": {
                "energy": 100.0,
                "proteins": 20.0,
                "carbohydrates": 30.0,
                "fat": 10.0,
                "fiber": 5.0,
            },
            "coverage": {
                "energy": 1,
                "proteins": 1,
                "carbohydrates": 1,
                "fat": 1,
                "fiber": 1,
            },
            "water_oz": 24.0,
            "water_target_oz": 140.0,
            "has_more": False,
        })

    output = render_week_csv455(reports, DAY)
    reader = csv.DictReader(io.StringIO(output))

    assert tuple(reader.fieldnames) == FIELDS

    rows = list(reader)
    assert len(rows) == 7

    for row in rows:
        for column in COVERAGE_COLUMN.values():
            assert row[column] == "1"

        assert row["calories_kcal"] == "100.0"
        assert row["protein_g"] == "20.0"
        assert row["carbohydrates_g"] == "30.0"
        assert row["fat_g"] == "10.0"
        assert row["fiber_g"] == "5.0"


# Release 456: explicit DEV gate, replay protection, and private writes.
def test_food_write456_disabled_by_default(browser):
    client, _ = browser
    login(client, 2)
    assert client.get("/secondary/food/new").status_code == 404
    assert client.post("/secondary/food/water").status_code == 404
    assert client.post("/secondary/food/entry").status_code == 404


def test_food_write456_water_and_food_isolation(browser, monkeypatch):
    from app.worker_food_write456 import form_payload456
    import uuid

    client, root = browser
    monkeypatch.setenv("TRACKER_SECONDARY_FOOD_WRITES456", "1")
    login(client, 2)

    page = client.get("/secondary/food/new")
    assert page.status_code == 200
    assert "Save Water" in page.text
    assert "Save Food" in page.text

    csrf = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        page.text,
    ).group(1)
    # Each form owns its own replay-protection token.
    # Do not depend on the number or order of forms
    # rendered on the mobile logging page.
    def submission_token_for(action):
        form_match = re.search(
            r'<form method="post" action="/secondary/food/'
            + re.escape(action)
            + r'"[^>]*>(.*?)</form>',
            page.text,
            re.S,
        )
        assert form_match, f"Missing {action} form"

        tokens = re.findall(
            r'name="submission_token"\s+value="([^"]+)"',
            form_match.group(1),
        )
        assert len(tokens) == 1
        return tokens[0]

    water_nonce = submission_token_for("water")
    food_nonce = submission_token_for("entry")

    assert water_nonce != food_nonce

    water = {
        "csrf_token": csrf,
        "submission_token": water_nonce,
        "day": DAY,
        "ounces": "8.5",
    }
    response = client.post(
        "/secondary/food/water",
        data=water,
        follow_redirects=False,
    )
    assert response.status_code == 303

    replay = client.post(
        "/secondary/food/water",
        data=water,
        follow_redirects=False,
    )
    assert replay.status_code == 409

    food = {
        "csrf_token": csrf,
        "submission_token": food_nonce,
        "day": DAY,
        "name": "Private Test Yogurt",
        "meal": "Breakfast",
        "servings": "2",
        "energy": "100",
        "proteins": "15",
        "carbohydrates": "",
        "fat": "2",
        "fiber": "",
    }

    response = client.post(
        "/secondary/food/entry",
        data=food,
        follow_redirects=False,
    )
    assert response.status_code == 303

    duplicate = client.post(
        "/secondary/food/entry",
        data=food,
        follow_redirects=False,
    )
    assert duplicate.status_code == 409

    own = client.get("/secondary/food?day=" + DAY)
    assert own.status_code == 200
    assert "Private Test Yogurt" in own.text
    assert "40.5 fl oz" in own.text

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db"
    ) as db:
        count = db.execute("""
            SELECT COUNT(*) FROM tracker_food_entries
        """).fetchone()[0]
        water_count = db.execute("""
            SELECT COUNT(*) FROM tracker_water_entries
        """).fetchone()[0]
    assert count == 2
    assert water_count == 2

    login(client, 3)
    other = client.get("/secondary/food?day=" + DAY)
    assert "Private Test Yogurt" not in other.text
    assert "12.0 fl oz" in other.text


def test_food_write456_csrf_validation_and_lockdown(
    browser, monkeypatch
):
    client, _ = browser
    monkeypatch.setenv("TRACKER_SECONDARY_FOOD_WRITES456", "1")
    login(client, 2)

    data = {
        "csrf_token": "invalid",
        "submission_token":
            "cc9e926a-0d75-4ef9-b1a4-7cc3fd124661",
        "day": DAY,
        "ounces": "12",
    }
    assert client.post(
        "/secondary/food/water", data=data
    ).status_code == 403

    data["user_id"] = "3"
    assert client.post(
        "/secondary/food/water", data=data
    ).status_code == 403

    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert client.get("/secondary/food/new").status_code == 404
    assert client.post(
        "/secondary/food/water", data=data
    ).status_code == 404


def test_food_write456_worker_rejects_extra_fields():
    from app.worker_food_write456 import parse_request456

    for raw in (
        b'{"action":"water","payload":{"user_id":3}}',
        b'{"action":"water","payload":{"sql":"SELECT"}}',
        b'{"action":"water","payload":{"database":"/tmp/x"}}',
        b'{"action":"food","payload":{}}',
        b'{"action":"water","action":"food","payload":{}}',
        b"z" * 5000,
    ):
        with pytest.raises(ValueError):
            parse_request456(raw)


def test_food_write456_prod_denial(browser, monkeypatch):
    client, _ = browser
    monkeypatch.setenv("TRACKER_SECONDARY_FOOD_WRITES456", "1")
    login(client, 2)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/food/new").status_code == 404
    assert client.post("/secondary/food/entry").status_code == 404


# Release 456 correction: normalized numeric values are
# serialized as strict worker-compatible strings.
def test_food_write456_parent_child_wire_contract(browser, monkeypatch):
    import uuid
    from types import SimpleNamespace

    from app.worker_food_write456 import (
        request_write456,
        parse_request456,
    )

    _, root = browser

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )

    captured = []

    def fake_worker_run(command, **kwargs):
        assert command[-1] == "app.worker_food_write456"

        message = kwargs["input"]
        captured.append(json.loads(message))

        action, payload = parse_request456(
            message.encode("utf-8")
        )

        assert action in ("water", "food")
        assert payload["day"] == DAY

        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "mode": "private-food-write456",
                "user_id": 2,
                "status": "created",
                "written": True,
            }),
        )

    monkeypatch.setattr(
        "app.worker_food_write456.subprocess.run",
        fake_worker_run,
    )

    water = {
        "day": DAY,
        "submission_token": str(uuid.uuid4()),
        "ounces": 8.5,
    }

    result = request_write456(
        2, "water", water, root
    )

    assert result["status"] == "created"
    assert captured[-1]["payload"]["ounces"] == "8.5"

    food = {
        "day": DAY,
        "submission_token": str(uuid.uuid4()),
        "name": "Wire Contract Yogurt",
        "meal": "Breakfast",
        "servings": 2.0,
        "nutrients": {
            "energy": 100.0,
            "proteins": 15.0,
            "carbohydrates": None,
            "fat": 2.0,
            "fiber": None,
        },
    }

    result = request_write456(
        2, "food", food, root
    )

    assert result["status"] == "created"
    assert captured[-1]["payload"]["servings"] == "2.0"
    assert captured[-1]["payload"]["energy"] == "100.0"
    assert captured[-1]["payload"]["proteins"] == "15.0"
    assert captured[-1]["payload"]["fiber"] == ""
    assert "nutrients" not in captured[-1]["payload"]


# Release 457: private saved-food reuse with replay protection.
def test_saved_food457_isolation_and_replay(browser, monkeypatch):
    client, root = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    login(client, 2)

    form = client.get("/secondary/food/new")
    assert form.status_code == 200
    assert "Quick Log Saved Food" in form.text
    assert "USER-TWO" in form.text
    assert "USER-THREE" not in form.text

    csrf = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        form.text,
    ).group(1)

    reuse = re.search(
        r'action="/secondary/food/reuse".*?'
        r'name="submission_token"\s+value="([^"]+)"',
        form.text,
        re.S,
    )
    assert reuse

    data = {
        "csrf_token": csrf,
        "submission_token": reuse.group(1),
        "product_id": "1",
        "day": DAY,
        "meal": "Lunch",
        "servings": "1",
    }

    result = client.post(
        "/secondary/food/reuse",
        data=data,
        follow_redirects=False,
    )
    assert result.status_code == 303

    again = client.post(
        "/secondary/food/reuse",
        data=data,
        follow_redirects=False,
    )
    assert again.status_code == 409

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db"
    ) as db:
        rows = db.execute("""
            SELECT product_id,meal,servings
            FROM tracker_food_entries ORDER BY id
        """).fetchall()

    assert rows == [
        (1, "Breakfast", 2.0),
        (1, "Lunch", 1.0),
    ]

    login(client, 3)
    other = client.get("/secondary/food/new")
    assert other.status_code == 200
    assert "USER-THREE" in other.text
    assert "USER-TWO" not in other.text

    other_day = client.get("/secondary/food?day=" + DAY)
    assert "USER-TWO" not in other_day.text
    assert "450.0 kcal" in other_day.text


def test_saved_food457_rejects_foreign_product_and_fields(
    browser, monkeypatch
):
    import uuid
    from app.worker_saved_food457 import (
        request_saved457, parse_request457
    )

    _, root = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )

    for raw in (
        b'{"action":"list","user_id":3}',
        b'{"action":"list","database":"/tmp/other.db"}',
        b'{"action":"reuse","payload":{"sql":"SELECT"}}',
        b'{"action":"list","action":"reuse"}',
        b"z" * 1000,
    ):
        with pytest.raises(ValueError):
            parse_request457(raw)

    with pytest.raises(PermissionError):
        request_saved457(1, "list", data_root=root)

    payload = {
        "product_id": 99999,
        "day": DAY,
        "meal": "Dinner",
        "servings": 1.0,
        "submission_token": str(uuid.uuid4()),
    }

    with pytest.raises(RuntimeError):
        request_saved457(2, "reuse", payload, root)

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db"
    ) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM tracker_food_entries
        """).fetchone()[0] == 1


def test_saved_food457_gate_lockdown_and_prod(
    browser, monkeypatch
):
    client, _ = browser
    login(client, 2)

    assert client.post("/secondary/food/reuse").status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )

    assert client.post(
        "/secondary/food/reuse",
        data={"csrf_token": "invalid"},
    ).status_code == 403

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get("/secondary/food/new").status_code == 404
    assert client.post("/secondary/food/reuse").status_code == 404

    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post("/secondary/food/reuse").status_code == 404


# Release 458: mobile shortcuts never create new write routes.
def test_mobile_quick_entry458_structure(browser, monkeypatch):
    from html.parser import HTMLParser

    client, _ = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    login(client, 2)

    response = client.get("/secondary/food/new")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    class MobileParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.forms = []
            self.current = None
            self.inputs = []
            self.presets = []

        def handle_starttag(self, tag, attributes):
            values = dict(attributes)
            if tag == "form":
                self.current = values.get("action")
                self.forms.append(self.current)
            elif tag == "input":
                self.inputs.append((self.current, values))
            elif (
                tag == "button"
                and "data-water-amount458" in values
            ):
                self.presets.append(
                    (self.current, values)
                )

        def handle_endtag(self, tag):
            if tag == "form":
                self.current = None

    parsed = MobileParser()
    parsed.feed(response.text)

    routes = (
        "/secondary/food/reuse",
        "/secondary/food/water",
        "/secondary/food/entry",
    )
    assert parsed.forms == list(routes)

    for route in routes:
        dates = [
            attrs for owner, attrs in parsed.inputs
            if owner == route
            and attrs.get("name") == "day"
        ]
        assert len(dates) == 1
        assert "data-journal-day458" in dates[0]

        tokens = [
            attrs for owner, attrs in parsed.inputs
            if owner == route
            and attrs.get("name") == "submission_token"
        ]
        assert len(tokens) == 1

    assert [
        attrs["data-water-amount458"]
        for owner, attrs in parsed.presets
    ] == ["8", "12", "16", "24", "32"]

    assert all(
        owner == "/secondary/food/water"
        and attrs["type"] == "button"
        and attrs["aria-pressed"] == "false"
        for owner, attrs in parsed.presets
    )

    assert 'document.querySelectorAll(' in response.text
    assert 'water.dataset' not in response.text
    assert 'button.dataset.waterAmount458' in response.text


def test_mobile_quick_entry458_no_new_write_permissions(
    browser, monkeypatch
):
    client, _ = browser
    login(client, 2)

    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    assert client.get("/secondary/food/new").status_code == 200

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    assert client.get("/secondary/food/new").status_code == 404


# Release 459: client-side filtering of private saved foods.
def test_mobile_saved_food_search459(browser, monkeypatch):
    from html.parser import HTMLParser

    client, _ = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    login(client, 2)

    response = client.get("/secondary/food/new")
    assert response.status_code == 200

    class Inspector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.form = None
            self.fields = []
            self.buttons = []
            self.options = []

        def handle_starttag(self, tag, attrs):
            data = dict(attrs)
            if tag == "form":
                self.form = data.get("action")
            if tag in ("input", "select"):
                self.fields.append((self.form, tag, data))
            if tag == "button":
                self.buttons.append((self.form, data))
            if tag == "option":
                self.options.append((self.form, data))

        def handle_endtag(self, tag):
            if tag == "form":
                self.form = None

    parser = Inspector()
    parser.feed(response.text)

    reuse = "/secondary/food/reuse"

    search = [
        attrs
        for owner, tag, attrs in parser.fields
        if owner == reuse
        and attrs.get("id") == "saved-food-search459"
    ]
    assert len(search) == 1
    assert search[0]["type"] == "search"
    assert "name" not in search[0]
    assert search[0]["autocomplete"] == "off"

    saved = [
        attrs
        for owner, tag, attrs in parser.fields
        if owner == reuse
        and attrs.get("id") == "saved-food-select459"
    ]
    assert len(saved) == 1
    assert saved[0]["name"] == "product_id"
    assert "required" in saved[0]

    submit = [
        attrs
        for owner, attrs in parser.buttons
        if owner == reuse
        and attrs.get("id") == "saved-food-submit459"
    ]
    assert len(submit) == 1
    assert submit[0]["type"] == "submit"

    assert "USER-TWO" in response.text
    assert "USER-THREE" not in response.text

    for expected in (
        'search459.addEventListener("input", filterSavedFoods459)',
        "select459.replaceChildren()",
        "option.textContent = item.label",
        "submit459.disabled =",
        'count459.textContent =',
    ):
        assert expected in response.text

    # Search only modifies client-side markup. Existing
    # write routes and server form fields are unchanged.
    assert parser.options
    assert response.headers["cache-control"] == "no-store"


def test_mobile_saved_food_search459_gates(browser, monkeypatch):
    client, _ = browser
    login(client, 2)

    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    assert client.get("/secondary/food/new").status_code == 200

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    assert client.get("/secondary/food/new").status_code == 404


def test_mobile_saved_food_search459_preserves_routes():
    from app.secondary_preview430 import preview_app

    routes = [
        (method, route.path)
        for route in preview_app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/food/")
    ]

    for route in (
        "/food/reuse",
        "/food/water",
        "/food/entry",
    ):
        assert routes.count(("POST", route)) == 1

    assert ("POST", "/food/search") not in routes


# Release 460: public barcode lookup, no private DB writes.
def test_barcode460_parse_and_basis():
    from app.secondary_barcode460 import (
        validate_barcode460,
        parse_product460,
        BarcodeNotFound460,
    )

    for code in (
        "", "abc", "01234", "012345678901234",
        "../private", "12345678?user_id=3",
    ):
        with pytest.raises(ValueError):
            validate_barcode460(code)

    code = "0123456789012"
    assert validate_barcode460(code) == code

    serving_data = {
        "status": 1,
        "product": {
            "product_name": "Test Yogurt",
            "serving_size": "150 g",
            "nutriments": {
                "energy-kcal_serving": 180,
                "proteins_serving": 15,
                "fat_serving": 2,
                "energy-kcal_100g": 120,
                "carbohydrates_100g": 12,
            },
        },
    }

    result = parse_product460(serving_data, code)
    assert result["basis"] == "per serving"
    assert result["nutrients"]["energy"] == 180
    assert result["nutrients"]["proteins"] == 15
    assert result["nutrients"]["carbohydrates"] is None

    per100 = {
        "status": 1,
        "product": {
            "product_name": "Test Snack",
            "nutriments": {
                "energy-kcal_100g": 230,
                "proteins_100g": 12,
            },
        },
    }

    other = parse_product460(per100, code)
    assert other["basis"] == "per 100 g"
    assert other["serving"] == "100 g"
    assert other["nutrients"]["energy"] == 230
    assert other["nutrients"]["fiber"] is None

    with pytest.raises(BarcodeNotFound460):
        parse_product460({"status": 0}, code)


def test_barcode460_authenticated_no_database_writes(
    browser, monkeypatch
):
    import app.secondary_preview430 as preview_module

    client, root = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )

    code = "0123456789012"
    calls = []

    def fake_lookup(value):
        calls.append(value)
        return {
            "barcode": code,
            "name": "Barcode Test Yogurt",
            "basis": "per serving",
            "serving": "150 g",
            "nutrients": {
                "energy": 180,
                "proteins": 15,
                "carbohydrates": None,
                "fat": 2,
                "fiber": None,
            },
            "source": "Open Food Facts",
            "warning": "Review product label",
        }

    monkeypatch.setattr(
        preview_module, "lookup_barcode460", fake_lookup
    )

    before = client.get(
        "/secondary/food/barcode?code=" + code
    )
    assert before.status_code == 401
    assert not calls

    login(client, 2)

    page = client.get("/secondary/food/new")
    assert page.status_code == 200
    assert "barcode-code460" in page.text
    assert "manual-food-form460" in page.text

    response = client.get(
        "/secondary/food/barcode?code=" + code
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["name"] == "Barcode Test Yogurt"
    assert calls == [code]

    with sqlite3.connect(
        root / "users" / "2" / "tracker.db"
    ) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM tracker_food_entries
        """).fetchone()[0] == 1

    login(client, 3)
    another = client.get(
        "/secondary/food/barcode?code=" + code
    )
    assert another.status_code == 200

    with sqlite3.connect(
        root / "users" / "3" / "tracker.db"
    ) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM tracker_food_entries
        """).fetchone()[0] == 1


def test_barcode460_input_gate_and_prod(browser, monkeypatch):
    client, _ = browser
    login(client, 2)

    code = "0123456789012"

    assert client.get(
        "/secondary/food/barcode?code=" + code
    ).status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )

    for suffix in (
        "",
        "?user_id=3",
        "?database=/tmp/x",
        "?code=abc",
        "?code=12345678&code=87654321",
        "?code=12345678&sql=SELECT",
    ):
        result = client.get(
            "/secondary/food/barcode" + suffix
        )
        assert result.status_code in (400, 422)

    assert client.post(
        "/secondary/food/barcode"
    ).status_code == 405

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get(
        "/secondary/food/barcode?code=" + code
    ).status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    assert client.get(
        "/secondary/food/barcode?code=" + code
    ).status_code == 404


# Release 461: optional browser camera scanning.
# Camera frames must never be uploaded to the Tracker server.
def test_camera_barcode461_mobile_markup(browser, monkeypatch):
    from html.parser import HTMLParser

    client, _ = browser
    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    login(client, 2)

    response = client.get("/secondary/food/new")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    class Inspect(HTMLParser):
        def __init__(self):
            super().__init__()
            self.form = None
            self.elements = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "form":
                self.form = values.get("action")
            self.elements.append(
                (self.form, tag, values)
            )

        def handle_endtag(self, tag):
            if tag == "form":
                self.form = None

    parser = Inspect()
    parser.feed(response.text)

    for element_id in (
        "barcode-scan461",
        "barcode-stop461",
    ):
        controls = [
            (owner, attrs)
            for owner, tag, attrs in parser.elements
            if tag == "button"
            and attrs.get("id") == element_id
        ]
        assert len(controls) == 1
        assert controls[0][0] is None
        assert controls[0][1]["type"] == "button"

    videos = [
        (owner, attrs)
        for owner, tag, attrs in parser.elements
        if tag == "video"
        and attrs.get("id") == "barcode-video461"
    ]

    assert len(videos) == 1
    assert videos[0][0] is None
    assert "playsinline" in videos[0][1]
    assert "hidden" in videos[0][1]

    sources = [
        attrs["src"]
        for owner, tag, attrs in parser.elements
        if tag == "script"
        and "src" in attrs
    ]

    assert (
        "/static/secondary_barcode_scan461.js?v=461"
        in sources
    )

    forms = [
        attrs["action"]
        for _, tag, attrs in parser.elements
        if tag == "form"
    ]
    assert forms == [
        "/secondary/food/reuse",
        "/secondary/food/water",
        "/secondary/food/entry",
    ]


def test_camera_barcode461_local_only_and_cleanup():
    from pathlib import Path

    script = Path(
        "app/static/secondary_barcode_scan461.js"
    ).read_text()

    for expected in (
        "navigator.mediaDevices.getUserMedia",
        "window.BarcodeDetector",
        '"environment"',
        "detector.detect(video)",
        "barcode.value = value",
        "lookup.click()",
        "track.stop()",
        'visibilitychange',
        '"pagehide"',
        '"barcode-stop461"',
        "ticket !== generation",
        "requestAnimationFrame",
    ):
        assert expected in script, expected

    # Scanner performs no HTTP request itself. The only
    # communication remains the existing barcode lookup.
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "sendBeacon",
        "MediaRecorder",
        "canvas.toDataURL",
        ".submit(",
        "requestSubmit(",
    ):
        assert forbidden not in script, forbidden

    assert "audio: false" in script
    assert '^[0-9]{8,14}$' in script


def test_camera_barcode461_preserves_feature_gates(
    browser, monkeypatch
):
    client, _ = browser
    login(client, 2)

    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    assert client.get("/secondary/food/new").status_code == 200

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get("/secondary/food/new").status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    assert client.get("/secondary/food/new").status_code == 404
