"""Release 708: all 19 remaining post-653 Workout unsafe routes.

Real Chromium browser obtains the genuine cookie-bound token and drives
missing/forged/valid writes against the same isolated 127.0.0.1 server. SQL
assertions read *only* /tmp/tracker-browser-qa.XXXXXXXX/data/tracker.db.
HTTP and HTTPS scenarios are intentionally sequential in a single test
because Tracker has a singleton active workout in the isolated database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

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
    raise RuntimeError("708 Workout acceptance requires isolated strict browser QA")

DB = DATA / "tracker.db"
ROUTES = frozenset({
    ("POST", "/workouts/backfill"),
    ("POST", "/workouts/backfill/import.csv"),
    ("POST", "/workouts/finish"),
    ("POST", "/workouts/finish-review"),
    ("POST", "/workouts/routines/{routine_id}/groups"),
    ("POST", "/workouts/routines/{routine_id}/groups/{group_id}/remove"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/move"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/substitute"),
    ("POST", "/workouts/routines/{routine_id}/program/import"),
    ("POST", "/workouts/routines/{routine_id}/program/import.csv"),
    ("POST", "/workouts/routines/{routine_id}/program/items/{item_id}"),
    ("POST", "/workouts/routines/{routine_id}/program/rest"),
    ("POST", "/workouts/routines/{routine_id}/start"),
    ("POST", "/workouts/sessions/{session_id}/sets/{set_id}/corrections/{change_id}/undo"),
    ("POST", "/workouts/sets"),
    ("POST", "/workouts/sets/repeat"),
    ("POST", "/workouts/sets/{set_id}/delete"),
    ("POST", "/workouts/sets/{set_id}/edit"),
    ("POST", "/workouts/start"),
})
assert len(ROUTES) == 19


def sql(query, args=()):
    if not DB.is_file() or DB.is_symlink() or DB.resolve().parent != DATA:
        raise AssertionError("Refusing to read anything outside disposable QA SQLite")
    with sqlite3.connect(DB, timeout=20) as db:
        return db.execute(query, args).fetchone()


def send(page, base, path, fields, csrf=None):
    kwargs = {"max_redirects": 0}
    if isinstance(fields, list):
        kwargs["data"] = urlencode(fields)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        kwargs["form"] = fields
        headers = {}
    if csrf is not None:
        headers["X-Tracker-CSRF"] = csrf
    if headers:
        kwargs["headers"] = headers
    return page.request.post(base + path, **kwargs)


def signed(page, base, token, path, fields, before, *, code=303):
    original = before()
    missing = send(page, base, path, fields)
    assert missing.status == 403, (path, "missing token", missing.status)
    assert before() == original, (path, "missing-token write committed")
    forged = send(page, base, path, fields, "forged-708-csrf-token")
    assert forged.status == 403, (path, "forged token", forged.status)
    assert before() == original, (path, "forged-token write committed")
    accepted = send(page, base, path, fields, token)
    assert accepted.status == code, (path, "valid signed", accepted.status,
                                      accepted.text()[:200])
    assert accepted.headers.get("x-tracker-csrf-report") == "valid"
    return accepted


def scenario(browser, base, scheme):
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        response = page.goto(base + "/workouts", wait_until="networkidle")
        assert response is not None and response.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert isinstance(token, str) and token.startswith("v1.")
        cookie = next((c for c in context.cookies()
                       if c["name"] == "tracker_csrf_v1"), None)
        assert cookie is not None and cookie["value"] == token
        assert sql("SELECT COUNT(*) FROM workout_sessions654 "
                   "WHERE completed_at IS NULL") == (0,)
        seen = set()

        unique = uuid4().hex[:12]
        ids = []
        for suffix in ("A", "B", "C"):
            name = f"QA708 {scheme} {unique} {suffix}"
            reply = send(page, base, "/workouts/equipment", {
                "name": name, "kind": "selectorized", "gym": "QA708 Disposable",
            }, token)
            assert reply.status == 303
            row = sql("SELECT id FROM workout_equipment654 WHERE name=?", (name,))
            assert row is not None
            ids.append(row[0])
        machine_a, machine_b, machine_c = ids

        routine = f"QA708 program {scheme} {unique}"
        assert send(page, base, "/workouts/routines", {"name": routine},
                    token).status == 303
        routine_id = sql("SELECT id FROM workout_routines655 WHERE name=?",
                         (routine,))[0]
        for machine in (machine_a, machine_b):
            assert send(page, base, f"/workouts/routines/{routine_id}/equipment",
                        {"equipment_id": str(machine)}, token).status == 303
        first = sql(
            "SELECT id,position FROM workout_routine_items655 "
            "WHERE routine_id=? AND equipment_id=?",
            (routine_id, machine_a),
        )
        second = sql(
            "SELECT id,position FROM workout_routine_items655 "
            "WHERE routine_id=? AND equipment_id=?",
            (routine_id, machine_b),
        )
        assert first is not None and second is not None
        first_id, second_id = first[0], second[0]
        assert first[1] < second[1]

        path = f"/workouts/routines/{routine_id}/program/rest"
        signed(page, base, token, path, {"rest_seconds": "120"},
               lambda: sql("SELECT rest_seconds FROM workout_routine_config667 "
                           "WHERE routine_id=?", (routine_id,)))
        seen.add(("POST", "/workouts/routines/{routine_id}/program/rest"))
        assert sql("SELECT rest_seconds FROM workout_routine_config667 "
                   "WHERE routine_id=?", (routine_id,)) == (120,)

        path = f"/workouts/routines/{routine_id}/program/items/{first_id}"
        signed(page, base, token, path, {
            "target_sets": "3", "target_reps": "10",
            "target_weight_lb": "80", "rest_seconds": "90",
            "setup_note": "QA708 initial goal",
        }, lambda: sql(
            "SELECT target_sets,target_reps,target_weight_lb,setup_note "
            "FROM workout_routine_targets667 WHERE routine_item_id=?",
            (first_id,),
        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/program/items/{item_id}"))
        assert sql(
            "SELECT target_sets,target_reps,target_weight_lb,setup_note "
            "FROM workout_routine_targets667 WHERE routine_item_id=?",
            (first_id,),
        ) == (3, 10, 80.0, "QA708 initial goal")

        path = f"/workouts/routines/{routine_id}/program/import"
        signed(page, base, token, path, {
            "targets_json": json.dumps({
                "version": 1,
                "targets": {str(first_id): {
                    "sets": "4", "reps": "11", "weight": "90",
                }},
            }),
        }, lambda: sql(
            "SELECT target_sets,target_reps,target_weight_lb "
            "FROM workout_routine_targets667 WHERE routine_item_id=?",
            (first_id,),
        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/program/import"))
        assert sql(
            "SELECT target_sets,target_reps,target_weight_lb "
            "FROM workout_routine_targets667 WHERE routine_item_id=?",
            (first_id,),
        ) == (4, 11, 90.0)

        path = f"/workouts/routines/{routine_id}/program/import.csv"
        csv_text = (
            "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n"
            f"{first_id},2,12,85,120,QA708 imported CSV\n"
        )
        signed(page, base, token, path, {"csv_text": csv_text},
               lambda: sql(
                   "SELECT target_sets,target_reps,target_weight_lb,setup_note "
                   "FROM workout_routine_targets667 WHERE routine_item_id=?",
                   (first_id,),
               ))
        seen.add(("POST", "/workouts/routines/{routine_id}/program/import.csv"))
        assert sql(
            "SELECT target_sets,target_reps,target_weight_lb,setup_note "
            "FROM workout_routine_targets667 WHERE routine_item_id=?",
            (first_id,),
        ) == (2, 12, 85.0, "QA708 imported CSV")

        path = f"/workouts/routines/{routine_id}/items/{second_id}/move"
        signed(page, base, token, path, {"direction": "up"},
               lambda: sql(
                   "SELECT position FROM workout_routine_items655 WHERE id=?",
                   (second_id,),
               ))
        seen.add(("POST", "/workouts/routines/{routine_id}/items/{item_id}/move"))
        assert sql(
            "SELECT position FROM workout_routine_items655 WHERE id=?",
            (second_id,),
        )[0] < sql(
            "SELECT position FROM workout_routine_items655 WHERE id=?",
            (first_id,),
        )[0]

        path = f"/workouts/routines/{routine_id}/items/{second_id}/substitute"
        signed(page, base, token, path, {"equipment_id": str(machine_c)},
               lambda: sql(
                   "SELECT equipment_id FROM workout_routine_items655 WHERE id=?",
                   (second_id,),
               ))
        seen.add(("POST", "/workouts/routines/{routine_id}/items/{item_id}/substitute"))
        assert sql(
            "SELECT equipment_id FROM workout_routine_items655 WHERE id=?",
            (second_id,),
        ) == (machine_c,)

        group_name = f"QA708 group {unique}"
        path = f"/workouts/routines/{routine_id}/groups"
        signed(page, base, token, path, [
            ("group_name", group_name), ("group_type", "superset"),
            ("rounds", "3"), ("item_ids", str(first_id)),
            ("item_ids", str(second_id)),
        ], lambda: sql(
            "SELECT COUNT(*) FROM workout_routine_groups668 "
            "WHERE routine_id=? AND group_name=?",
            (routine_id, group_name),
        ))
        seen.add(("POST", "/workouts/routines/{routine_id}/groups"))
        group = sql(
            "SELECT id FROM workout_routine_groups668 "
            "WHERE routine_id=? AND group_name=?",
            (routine_id, group_name),
        )
        assert group is not None
        group_id = group[0]
        assert sql(
            "SELECT COUNT(*) FROM workout_routine_group_members668 "
            "WHERE group_id=?", (group_id,),
        ) == (2,)

        path = f"/workouts/routines/{routine_id}/groups/{group_id}/remove"
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT COUNT(*) FROM workout_routine_groups668 WHERE id=?",
                   (group_id,),
               ))
        seen.add(("POST", "/workouts/routines/{routine_id}/groups/{group_id}/remove"))
        assert sql(
            "SELECT COUNT(*) FROM workout_routine_groups668 WHERE id=?",
            (group_id,),
        ) == (0,)

        path = f"/workouts/routines/{routine_id}/start"
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT COUNT(*) FROM workout_session_routines655 "
                   "WHERE routine_id=?", (routine_id,),
               ))
        seen.add(("POST", "/workouts/routines/{routine_id}/start"))
        active = sql(
            "SELECT s.id FROM workout_sessions654 s "
            "JOIN workout_session_routines655 r ON r.session_id=s.id "
            "WHERE s.completed_at IS NULL AND r.routine_id=?",
            (routine_id,),
        )
        assert active is not None
        session_id = active[0]

        path = "/workouts/sets"
        signed(page, base, token, path, {
            "equipment_id": str(machine_a), "weight_lb": "95",
            "reps": "10", "effort": "7",
        }, lambda: sql(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ))
        seen.add(("POST", "/workouts/sets"))
        logged = sql(
            "SELECT id,weight_lb,reps FROM workout_sets654 "
            "WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        assert logged is not None and logged[1:] == (95.0, 10)
        set_id = logged[0]

        path = f"/workouts/sets/{set_id}/edit"
        signed(page, base, token, path, {
            "weight_lb": "97.5", "reps": "11",
            "effort": "7", "set_type": "working",
        }, lambda: sql(
            "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?",
            (set_id,),
        ))
        seen.add(("POST", "/workouts/sets/{set_id}/edit"))
        assert sql(
            "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?",
            (set_id,),
        ) == (97.5, 11)

        path = "/workouts/sets/repeat"
        signed(page, base, token, path, {
            "equipment_id": str(machine_a), "source_set_id": str(set_id),
        }, lambda: sql(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ))
        seen.add(("POST", "/workouts/sets/repeat"))
        assert sql(
            "SELECT COUNT(*) FROM workout_sets654 WHERE session_id=?",
            (session_id,),
        ) == (2,)
        repeated = sql(
            "SELECT id FROM workout_sets654 WHERE session_id=? AND id !=?",
            (session_id, set_id),
        )
        assert repeated is not None

        path = f"/workouts/sets/{repeated[0]}/delete"
        signed(page, base, token, path, {"confirm_delete": "yes"},
               lambda: sql(
                   "SELECT COUNT(*) FROM workout_sets654 WHERE id=?",
                   (repeated[0],),
               ))
        seen.add(("POST", "/workouts/sets/{set_id}/delete"))
        assert sql(
            "SELECT COUNT(*) FROM workout_sets654 WHERE id=?",
            (repeated[0],),
        ) == (0,)

        path = "/workouts/finish"
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT completed_at FROM workout_sessions654 WHERE id=?",
                   (session_id,),
               ))
        seen.add(("POST", "/workouts/finish"))
        assert sql(
            "SELECT completed_at FROM workout_sessions654 WHERE id=?",
            (session_id,),
        )[0] is not None

        # Previously qualified 707 correction creates one authenticated
        # audit record. The NEW 708 undo route must reverse that exact row.
        correction = send(
            page, base,
            f"/workouts/sessions/{session_id}/sets/{set_id}/correct",
            {"weight_lb": "100", "reps": "9", "effort": "7",
             "set_type": "working", "reason": "QA708 audited correction"},
            token,
        )
        assert correction.status == 303
        change = sql(
            "SELECT id FROM workout_set_corrections668 WHERE set_id=? "
            "ORDER BY id DESC LIMIT 1", (set_id,),
        )
        assert change is not None
        path = (
            f"/workouts/sessions/{session_id}/sets/{set_id}/"
            f"corrections/{change[0]}/undo"
        )
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?",
                   (set_id,),
               ))
        seen.add(("POST", "/workouts/sessions/{session_id}/sets/{set_id}/corrections/{change_id}/undo"))
        assert sql(
            "SELECT weight_lb,reps FROM workout_sets654 WHERE id=?", (set_id,),
        ) == (97.5, 11)
        assert sql(
            "SELECT COUNT(*) FROM workout_set_corrections668 WHERE set_id=?",
            (set_id,),
        ) == (2,)

        path = "/workouts/start"
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL",
               ))
        seen.add(("POST", "/workouts/start"))
        free_id = sql(
            "SELECT id FROM workout_sessions654 WHERE completed_at IS NULL"
        )[0]
        assert free_id != session_id
        # A finish-review endpoint works even without logged sets; it must
        # record the actual completion and navigate to the review.
        path = "/workouts/finish-review"
        signed(page, base, token, path, {},
               lambda: sql(
                   "SELECT completed_at FROM workout_sessions654 WHERE id=?",
                   (free_id,),
               ))
        seen.add(("POST", "/workouts/finish-review"))
        assert sql(
            "SELECT completed_at FROM workout_sessions654 WHERE id=?", (free_id,),
        )[0] is not None

        # Real historical rows; unique clock windows for both schemes.
        for variant, route in enumerate(
            ("/workouts/backfill", "/workouts/backfill/import.csv")
        ):
            hour = 8 + variant * 2 + (0 if scheme == "http" else 1)
            start_time, end_time = f"{hour:02d}:00", f"{hour:02d}:45"
            day = "2026-11-15"
            previous = lambda: sql(
                "SELECT COUNT(*) FROM workout_sessions654 "
                "WHERE date(started_at)=? AND time(started_at)=?",
                (day, start_time + ":00"),
            )
            if variant == 0:
                fields = {
                    "day": day, "start_time": start_time,
                    "end_time": end_time, "equipment_id": str(machine_a),
                    "weight_lb": "50", "reps": "10",
                    "effort": "5", "set_time": f"{hour:02d}:15",
                }
            else:
                fields = {
                    "day": day, "start_time": start_time,
                    "end_time": end_time,
                    "csv_text": (
                        "equipment_id,weight_lb,reps,effort,set_time,set_type\n"
                        f"{machine_a},55,12,5,{hour:02d}:15,working\n"
                    ),
                }
            signed(page, base, token, route, fields, previous)
            seen.add(("POST", route))
            assert previous() == (1,)
            assert sql(
                "SELECT COUNT(*) FROM workout_sets654 w "
                "JOIN workout_sessions654 s ON w.session_id=s.id "
                "WHERE date(s.started_at)=? AND time(s.started_at)=?",
                (day, start_time + ":00"),
            ) == (1,)

        assert seen == ROUTES, ("Wrong qualified route set", seen ^ ROUTES)
        assert sql(
            "SELECT COUNT(*) FROM workout_sessions654 WHERE completed_at IS NULL"
        ) == (0,)
        print("CSRF_708_REMAINING_WORKOUT_SIGNED_POSITIVE_ROUTES=19", flush=True)
    finally:
        context.close()


def test_708_remaining_nineteen_workout_writes_http_https_sequential():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            scenario(browser, HTTP_URL, "http")
            scenario(browser, HTTPS_URL, "https")
        finally:
            browser.close()
