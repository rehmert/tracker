"""Release 667: Chromium mobile program editing and deliberate gym-goal application."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect, sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = (ROOT / "app/templates/workout_program667.html").read_text(encoding="utf-8")
QUICK = (ROOT / "app/templates/workout_quick659.html").read_text(encoding="utf-8")
PROGRAM_BODY = PROGRAM.split("{% block content %}", 1)[1].rsplit("{% endblock %}", 1)[0]
QUICK_BODY = QUICK.split("{% block content %}", 1)[1].rsplit("{% endblock %}", 1)[0]
CSS_PROGRAM = (ROOT / "app/static/css/tracker-workout-program667.css").read_text(encoding="utf-8")
JS_PROGRAM = (ROOT / "app/static/js/tracker-workout-program667.js").read_text(encoding="utf-8")
CSS659 = (ROOT / "app/static/css/tracker-workouts659.css").read_text(encoding="utf-8")
CSS666 = (ROOT / "app/static/css/tracker-workout-targets666.css").read_text(encoding="utf-8")
CSS667 = (ROOT / "app/static/css/tracker-workout-gym667.css").read_text(encoding="utf-8")
JS659 = (ROOT / "app/static/js/tracker-workouts659.js").read_text(encoding="utf-8")
JS667 = (ROOT / "app/static/js/tracker-workout-gym667.js").read_text(encoding="utf-8")
PROGRAM_URL = "https://tracker.test/workouts/routines/99/program"
GYM_URL = "https://tracker.test/workouts/quick?machine=50"


def page667(body, css, js):
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0;padding:12px}'
        + css + '</style></head><body>'
        + body + '<script>' + js + '</script></body></html>'
    )


def program_fixture667():
    routine = SimpleNamespace(id=99, name="Upper A")
    machine = SimpleNamespace(
        id=50, name="Seated Press", gym="East Gym", seat_setting="3",
        setup_notes="Keep shoulders stable",
    )
    last = SimpleNamespace(
        session_id=4, started_at=datetime(2026, 11, 16, 9),
        sets=3, heaviest_lb=95.0,
    )
    rows = [{
        "item": SimpleNamespace(id=701), "equipment": machine,
        "latest": last, "previous": None,
    }]
    goal = SimpleNamespace(
        target_sets=3, target_reps=10, target_weight_lb=100.0,
        setup_note="Seat 3 / neutral grip", rest_seconds=120,
    )
    body = templates.env.from_string(PROGRAM_BODY).render(
        routine=routine, rows=rows, targets={701:goal},
        default_rest=90, rest_choices=(30,45,60,75,90,120,150,180,240,300,360,420,480,600),
    )
    return page667(body, CSS_PROGRAM, JS_PROGRAM)


def gym_fixture667():
    machine = SimpleNamespace(
        id=50, name="Seated Press", gym="East Gym",
        seat_setting="3", setup_notes="Keep shoulders stable",
    )
    snapshot = SimpleNamespace(
        target_sets=3, target_reps=10, target_weight_lb=100.0,
        setup_note="Seat 3 / neutral grip", rest_seconds=120,
    )
    history = SimpleNamespace(
        id=900, weight_lb=90.0, reps=8, effort=5,
    )
    body = templates.env.from_string(QUICK_BODY).render(
        request=SimpleNamespace(query_params={}),
        active=SimpleNamespace(id=888),
        machine=machine, equipment=[machine],
        routines=[], routine=SimpleNamespace(id=99, name="Upper A"),
        plan_item_id=701, frozen_goal=snapshot, current_goal=None,
        goal_progress667=dict(
            credited_sets=2, working_sets=2, warmup_sets=1,
            progress_percent=67, achieved=False,
        ),
        rest_seconds667=120, routine_logged=1, routine_total=1,
        machine_sets=[], last=history, previous_machine=None, next_machine=None,
    )
    return page667(
        body, CSS659 + CSS666 + CSS667, JS659 + "\n" + JS667,
    )


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320,740),(390,844),(393,852)])
def test_667_mobile_program_and_explicit_browser_import(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors, imports = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        context.route("**/workouts/routines/99/program/import", lambda route: (
            imports.append((route.request.method, route.request.post_data)),
            route.fulfill(status=200, content_type="text/plain; charset=utf-8", body="Captured")
        ))
        context.route("**/workouts/routines/99/program", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body=program_fixture667(),
        ))
        try:
            page.goto(PROGRAM_URL)
            assert page.evaluate("document.characterSet") == "UTF-8"
            expect(page.get_by_role("heading", name="Upper A — Workout Program")).to_be_visible()
            expect(page.locator('input[name="target_sets"]')).to_have_value("3")
            expect(page.locator('input[name="target_weight_lb"]')).to_have_value("100.0")
            expect(page.locator('textarea[name="setup_note"]')).to_have_value(
                "Seat 3 / neutral grip"
            )
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"Program overflows {width}px"
            page.evaluate("""() => localStorage.setItem(
                'tracker.workout665.plan.routine.99',
                JSON.stringify({version:1,targets:{
                    701:{sets:'4',reps:'8',weight:'105'}
                }})
            )""")
            page.get_by_role("button", name="Import This Browser's Targets").click()
            expect(page.get_by_text("Captured")).to_be_visible()
            assert len(imports) == 1 and imports[0][0] == "POST"
            submitted = parse_qs(imports[0][1])
            assert "targets_json" in submitted
            assert '"weight":"105"' in submitted["targets_json"][0]
            assert not errors, errors
        finally:
            context.close()
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320,740),(390,844),(393,852)])
def test_667_mobile_quick_goals_copy_only_on_click_and_show_set_type(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors, writes = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: (
            writes.append(request.url) if request.method != "GET" else None
        ))
        context.route("**/workouts/quick*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=gym_fixture667(),
        ))
        try:
            page.goto(GYM_URL)
            expect(page.get_by_role("heading", name="This session's frozen goal")).to_be_visible()
            expect(page.locator("#workout667-active-goal")).to_be_visible()
            expect(page.locator("#workout666-targets")).to_have_count(0)
            expect(page.locator("#workout659-weight")).to_have_value("90.0")
            expect(page.locator("#workout659-reps")).to_have_value("8")
            expect(page.locator("#workout659-rest-duration")).to_have_value("120")
            expect(page.locator("#workout659-log-form")).to_have_attribute(
                "action", "/workouts/quick/sets",
            )
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"Gym overflows {width}px"
            page.get_by_role("button", name="Use planned weight & reps").click()
            expect(page.locator("#workout659-weight")).to_have_value("100")
            expect(page.locator("#workout659-reps")).to_have_value("10")
            page.locator('input[name="set_type"][value="warmup"]').check()
            expect(page.locator('input[name="set_type"][value="warmup"]')).to_be_checked()
            expect(page.locator("#workout659-save")).to_be_enabled()
            assert writes == [], writes
            assert not errors, errors
        finally:
            context.close()
            browser.close()
