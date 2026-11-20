"""Release 707: 17 Workout writes with signed persistence and forged denials.

Exercises real HTTP and HTTPS Chromium contexts SEQUENTIALLY because Tracker
has one active workout per scoped SQLite DB. All data is synthetic and the
browser-qualifier's DB root must be under /tmp/tracker-browser-qa.XXXXXXXX.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(HTTP_URL), urlsplit(HTTPS_URL)
if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data" and DATA.is_dir() and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("707 Workout acceptance requires strictly disposable Chromium QA")
DB = DATA / "tracker.db"
pytestmark = pytest.mark.browser

WORKOUT_ROUTES = frozenset({
    ("POST", "/workouts/equipment"),
    ("POST", "/workouts/equipment/{equipment_id}/settings"),
    ("POST", "/workouts/equipment/{equipment_id}/load"),
    ("POST", "/workouts/routines"),
    ("POST", "/workouts/routines/{routine_id}/equipment"),
    ("POST", "/workouts/routines/{routine_id}/schedule"),
    ("POST", "/workouts/routines/{routine_id}/schedule/clear"),
    ("POST", "/workouts/routines/{routine_id}/duplicate"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/remove"),
    ("POST", "/workouts/quick/routines/{routine_id}/start"),
    ("POST", "/workouts/quick/sets"),
    ("POST", "/workouts/quick/repeat"),
    ("POST", "/workouts/quick/finish"),
    ("POST", "/workouts/sessions/{session_id}/sets/{set_id}/correct"),
    ("POST", "/workouts/sessions/{session_id}/reuse-as-routine"),
    ("POST", "/workouts/quick/start"),
    ("POST", "/workouts/quick/offline-sync"),
})
assert len(WORKOUT_ROUTES) == 17


def read(sql, params=()):
    if (not DB.is_file() or DB.is_symlink()
            or DB.resolve().parent != DATA):
        raise AssertionError("Unexpected SQLite source for Workout evidence")
    with sqlite3.connect(DB, timeout=20) as conn:
        return conn.execute(sql, params).fetchone()


def required_signed(page, base, token, route, data, before, *,
                    success_status=303):
    """Check same payload denied twice, unchanged DB, then signed write."""
    previous = before()
    missing = page.request.post(base + route, form=data, max_redirects=0)
    assert missing.status == 403, (route, "missing", missing.status)
    assert before() == previous, (route, "missing request mutated database")
    forged = page.request.post(
        base + route, form=data, max_redirects=0,
        headers={"X-Tracker-CSRF": "forged-707-workout-token"},
    )
    assert forged.status == 403, (route, "forged", forged.status)
    assert before() == previous, (route, "forged request mutated database")
    accepted = page.request.post(
        base + route, form=data, max_redirects=0,
        headers={"X-Tracker-CSRF": token},
    )
    assert accepted.status == success_status, (
        route, "valid signed write", accepted.status,
        accepted.text()[:280],
    )
    assert accepted.headers.get("x-tracker-csrf-report") == "valid"
    return accepted


def workout_scenario(browser, base, scheme):
    context = browser.new_context(ignore_https_errors=True)
    seen = set()
    try:
        page = context.new_page()
        landing = page.goto(base + "/workouts", wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")
        cookie = next((c for c in context.cookies() if c["name"] == "tracker_csrf_v1"), None)
        assert cookie is not None and cookie["value"] == token
        form = page.locator('form[action="/workouts/equipment"][method="post" i]').first
        assert form.count() == 1
        assert form.locator('input[name="csrf_token"]').input_value() == token

        # No previously unfinished workout is allowed to pollute this
        # independent isolated source database.
        assert read(
            "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL"
        ) == (0,), "Isolated full-gate fixture left an unfinished workout"

        unique = uuid4().hex[:12]
        machine = "QA707 Machine " + scheme + " " + unique
        route = "/workouts/equipment"
        required_signed(page, base, token, route, {
            "name": machine, "kind": "selectorized", "gym": "QA707 Synthetic Gym",
        }, lambda: read(
            "SELECT COUNT(*) FROM workout_equipment654 WHERE name=?", (machine,),
        ))
        seen.add(("POST", route))
        row = read("SELECT id,kind FROM workout_equipment654 WHERE name=?", (machine,))
        assert row is not None and row[1] == "selectorized"
        equipment_id = row[0]

        route = f"/workouts/equipment/{equipment_id}/settings"
        required_signed(page, base, token, route, {
            "seat_setting": "4", "setup_notes": "QA707 machine setting",
        }, lambda: read(
            "SELECT seat_setting,setup_notes FROM workout_equipment654 WHERE id=?",
            (equipment_id,),
        ))
        seen.add(("POST", "/workouts/equipment/{equipment_id}/settings"))
        assert read(
            "SELECT seat_setting,setup_notes FROM workout_equipment654 WHERE id=?",
            (equipment_id,),
        ) == ("4", "QA707 machine setting")

        route = f"/workouts/equipment/{equipment_id}/load"
        required_signed(page, base, token, route, {
            "load_mode": "stack", "multiplier": "1.5",
            "offset_lb": "5", "note": "QA707 units",
        }, lambda: read(
            "SELECT multiplier,offset_lb,note FROM workout_equipment_load668 "
            "WHERE equipment_id=?", (equipment_id,),
        ))
        seen.add(("POST", "/workouts/equipment/{equipment_id}/load"))
        assert read(
            "SELECT load_mode,multiplier,offset_lb,note FROM workout_equipment_load668 "
            "WHERE equipment_id=?", (equipment_id,),
        ) == ("stack", 1.5, 5.0, "QA707 units")

        routine = "QA707 Routine " + scheme + " " + unique
        required_signed(page, base, token, "/workouts/routines",
                        {"name": routine},
                        lambda: read("SELECT COUNT(*) FROM workout_routines655 WHERE name=?",
                                     (routine,)))
        seen.add(("POST", "/workouts/routines"))
        routine_id = read(
            "SELECT id FROM workout_routines655 WHERE name=?", (routine,),
        )[0]

        route = f"/workouts/routines/{routine_id}/equipment"
        required_signed(page, base, token, route,
                        {"equipment_id": str(equipment_id)},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_routine_items655 WHERE routine_id=?",
                            (routine_id,),
                        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/equipment"))
        item_id = read(
            "SELECT id FROM workout_routine_items655 WHERE routine_id=? AND equipment_id=?",
            (routine_id, equipment_id),
        )[0]

        route = f"/workouts/routines/{routine_id}/schedule"
        required_signed(page, base, token, route,
                        {"weekdays": "0,2", "start_on": "2026-11-15"},
                        lambda: read(
                            "SELECT weekdays,start_on FROM workout_routine_schedule668 "
                            "WHERE routine_id=?", (routine_id,),
                        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/schedule"))
        assert read(
            "SELECT weekdays,start_on FROM workout_routine_schedule668 WHERE routine_id=?",
            (routine_id,),
        ) == ("0,2", "2026-11-15")

        route = f"/workouts/routines/{routine_id}/schedule/clear"
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_routine_schedule668 WHERE routine_id=?",
                            (routine_id,),
                        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/schedule/clear"))
        assert read(
            "SELECT COUNT(*) FROM workout_routine_schedule668 WHERE routine_id=?",
            (routine_id,),
        ) == (0,)

        route = f"/workouts/routines/{routine_id}/duplicate"
        name_copy = routine + " (Copy)"
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_routines655 WHERE name=?",
                            (name_copy,),
                        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/duplicate"))
        copied = read("SELECT id FROM workout_routines655 WHERE name=?", (name_copy,))
        assert copied is not None and copied[0] != routine_id
        copy_id = copied[0]
        copied_item_id = read(
            "SELECT id FROM workout_routine_items655 WHERE routine_id=?",
            (copy_id,),
        )[0]

        route = f"/workouts/routines/{copy_id}/items/{copied_item_id}/remove"
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_routine_items655 WHERE routine_id=?",
                            (copy_id,),
                        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/items/{item_id}/remove"))
        assert read(
            "SELECT COUNT(*) FROM workout_routine_items655 WHERE routine_id=?",
            (copy_id,),
        ) == (0,)
        assert read(
            "SELECT COUNT(*) FROM workout_routine_items655 WHERE routine_id=?",
            (routine_id,),
        ) == (1,)

        route = f"/workouts/quick/routines/{routine_id}/start"
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_session_routines655 WHERE routine_id=?",
                            (routine_id,),
                        ))
        seen.add(("POST", "/workouts/quick/routines/{routine_id}/start"))
        session = read(
            "SELECT s.id FROM workout_sessions654 s JOIN workout_session_routines655 r "
            "ON s.id=r.session_id WHERE r.routine_id=? AND s.completed_at IS NULL",
            (routine_id,),
        )
        assert session is not None
        session_id = session[0]

        route = "/workouts/quick/sets"
        required_signed(page, base, token, route, {
            "equipment_id": str(equipment_id), "weight_lb": "95.5",
            "reps": "12", "effort": "7",
        }, lambda: read(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ))
        seen.add(("POST", "/workouts/quick/sets"))
        logged = read(
            "SELECT id,weight_lb,reps,effort FROM workout_sets654 "
            "WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        assert logged is not None and logged[1:] == (95.5, 12, 7)
        set_id = logged[0]

        route = "/workouts/quick/repeat"
        required_signed(page, base, token, route, {
            "equipment_id": str(equipment_id), "source_set_id": str(set_id),
        }, lambda: read(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ))
        seen.add(("POST", "/workouts/quick/repeat"))
        assert read(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ) == (2,)

        # Release 668 offline-sync must actually persist one unique
        # performed_at set, reject forgery, and replay idempotently.
        route = "/workouts/quick/offline-sync"
        key = str(uuid4())
        fields = {
            "session_id": str(session_id), "equipment_id": str(equipment_id),
            "client_key": key, "weight_lb": "70", "reps": "10",
            "performed_at": datetime.now(timezone.utc).isoformat(),
            "set_type": "working",
        }
        saved = required_signed(
            page, base, token, route, fields,
            lambda: read(
                "SELECT COUNT(*) FROM workout_offline_receipts668 WHERE client_key=?",
                (key,),
            ), success_status=200,
        )
        seen.add(("POST", "/workouts/quick/offline-sync"))
        assert saved.json()["ok"] is True and saved.json()["duplicate"] is False
        assert read(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ) == (3,)
        replayed = page.request.post(
            base + route, form=fields, max_redirects=0,
            headers={"X-Tracker-CSRF": token},
        )
        assert replayed.status == 200 and replayed.json()["duplicate"] is True
        assert read(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ) == (3,)

        route = "/workouts/quick/finish"
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT completed_at FROM workout_sessions654 WHERE id=?",
                            (session_id,),
                        ))
        seen.add(("POST", "/workouts/quick/finish"))
        assert read(
            "SELECT completed_at FROM workout_sessions654 WHERE id=?",
            (session_id,),
        )[0] is not None

        route = f"/workouts/sessions/{session_id}/sets/{set_id}/correct"
        required_signed(page, base, token, route, {
            "weight_lb": "97.5", "reps": "10",
            "effort": "7", "set_type": "working",
            "reason": "QA707 correction",
        }, lambda: read(
            "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?",
            (set_id,),
        ))
        seen.add(("POST", "/workouts/sessions/{session_id}/sets/{set_id}/correct"))
        assert read(
            "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?",
            (set_id,),
        ) == (97.5, 10)
        assert read(
            "SELECT COUNT(*) FROM workout_set_corrections668 WHERE set_id=?",
            (set_id,),
        ) == (1,)

        route = f"/workouts/sessions/{session_id}/reuse-as-routine"
        before_count = lambda: read("SELECT COUNT(*) FROM workout_routines655")
        snapshot = before_count()
        required_signed(page, base, token, route, {}, before_count)
        seen.add(("POST", "/workouts/sessions/{session_id}/reuse-as-routine"))
        assert before_count()[0] == snapshot[0] + 1

        route = "/workouts/quick/start"
        previous = read(
            "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL"
        )
        assert previous == (0,)
        required_signed(page, base, token, route, {},
                        lambda: read(
                            "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL",
                        ))
        seen.add(("POST", "/workouts/quick/start"))
        free = read(
            "SELECT id FROM workout_sessions654 WHERE completed_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
        )
        assert free is not None and free[0] != session_id
        # Leave no active workout to interfere with subsequent strict
        # acceptance modules in this disposable shared SQLite database.
        finish = page.request.post(
            base + "/workouts/quick/finish", form={}, max_redirects=0,
            headers={"X-Tracker-CSRF": token},
        )
        assert finish.status == 303
        assert read(
            "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL"
        ) == (0,)

        assert seen == WORKOUT_ROUTES
        print("CSRF_707_WORKOUT_SIGNED_POSITIVE_ROUTES=17", flush=True)
    finally:
        context.close()


def test_707_workout_sequential_http_https_real_signed_lifecycles():
    # One test rather than two xdist-dispatched cases: active workout is
    # intentionally singleton in the isolated scoped database.
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            workout_scenario(browser, HTTP_URL, "http")
            workout_scenario(browser, HTTPS_URL, "https")
        finally:
            browser.close()
