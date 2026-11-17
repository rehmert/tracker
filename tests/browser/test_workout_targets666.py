"""Release 666: mobile Chromium view of real Rapid Gym markup and local plan IDs."""
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[2]
QUICK = (ROOT / "app/templates/workout_quick659.html").read_text(encoding="utf-8")
BODY = QUICK.split("{% block content %}", 1)[1].rsplit("{% endblock %}", 1)[0]
CSS659 = (ROOT / "app/static/css/tracker-workouts659.css").read_text(encoding="utf-8")
CSS662 = (ROOT / "app/static/css/tracker-workouts662.css").read_text(encoding="utf-8")
CSS666 = (ROOT / "app/static/css/tracker-workout-targets666.css").read_text(encoding="utf-8")
JS666 = (ROOT / "app/static/js/tracker-workout-targets666.js").read_text(encoding="utf-8")
URL = "https://tracker.test/workouts/quick?machine=50"


def fixture666(machine_id=50, routine_id=99):
    machines = [
        SimpleNamespace(id=50, name="Press", gym="East Gym", seat_setting="",
                        setup_notes=""),
        SimpleNamespace(id=51, name="Row", gym="East Gym", seat_setting="",
                        setup_notes=""),
        SimpleNamespace(id=52, name="Unrelated Machine", gym="Other Gym",
                        seat_setting="", setup_notes=""),
    ]
    selected = next(item for item in machines if item.id == machine_id)
    item_id = {50: 701, 51: 702}.get(machine_id) if routine_id else None
    routine = SimpleNamespace(id=routine_id, name="Upper A") if routine_id else None
    last = SimpleNamespace(id=901, weight_lb=90.0, reps=8, effort=5)
    html = templates.env.from_string(BODY).render(
        request=SimpleNamespace(query_params={}),
        active=SimpleNamespace(id=888),
        last=last, machine=selected, equipment=machines,
        routines=[], routine=routine, plan_item_id=item_id,
        routine_logged=0, routine_total=2, machine_sets=[],
        previous_machine=None, next_machine=None,
    )
    return (
        '<!doctype html><html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0;padding:12px}'
        + CSS659 + CSS662 + CSS666 + '</style></head><body>'
        + html + '<script>' + JS666 + '</script></body></html>'
    )


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320, 740), (390, 844), (393, 852)])
def test_666_phone_browser_only_targets_show_correct_routine_item_without_modifying_set_inputs(width, height):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))

        def serve(route):
            params = parse_qs(urlsplit(route.request.url).query)
            machine = int(params.get("machine", ["50"])[0])
            routine = None if params.get("free") == ["1"] else int(
                params.get("routine", ["99"])[0]
            )
            route.fulfill(
                status=200, content_type="text/html; charset=utf-8",
                body=fixture666(machine, routine),
            )

        # Shared context routing covers both the main page and the new tab.
        # A page-scoped mock would let the second tab resolve tracker.test.
        context.route("**/workouts/quick*", serve)
        try:
            page.goto(URL)
            assert page.evaluate("document.characterSet") == "UTF-8"
            panel = page.locator("#workout666-targets")
            expect(panel).to_be_visible()
            expect(panel).to_have_attribute("data-routine-id666", "99")
            expect(panel).to_have_attribute("data-item-id666", "701")
            expect(page.get_by_role("link", name="Edit plan")).to_have_attribute(
                "href", "/workouts/routines/99/plan"
            )
            expect(page.locator("#workout666-target-values")).to_be_hidden()
            expect(page.locator("#workout666-targets-status")).to_contain_text(
                "No saved targets"
            )

            # Exactly the format written by the Release 665 planner.
            page.evaluate("""() => localStorage.setItem(
                'tracker.workout665.plan.routine.99',
                JSON.stringify({version:1, targets:{
                    701:{sets:'3', reps:'10', weight:'102.5'},
                    702:{sets:'4', reps:'12', weight:'70'}
                }})
            )""")
            page.reload()
            panel = page.locator("#workout666-targets")
            expect(panel.locator('[data-target666="sets"]')).to_have_text("3")
            expect(panel.locator('[data-target666="reps"]')).to_have_text("10")
            expect(panel.locator('[data-target666="weight"]')).to_have_text("102.5 lb")
            expect(page.locator("#workout666-target-values")).to_be_visible()
            expect(page.locator("#workout666-targets-status")).to_contain_text(
                "not logged"
            )
            # Read-only targets never seed real workout data-entry controls.
            expect(page.locator("#workout659-weight")).to_have_value("90.0")
            expect(page.locator("#workout659-reps")).to_have_value("8")
            expect(page.locator("#workout659-log-form")).to_have_attribute(
                "action", "/workouts/quick/sets"
            )
            expect(page.locator("#workout659-save")).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"Rapid Gym overflows {width}px"

            page.goto("https://tracker.test/workouts/quick?machine=51")
            panel = page.locator("#workout666-targets")
            expect(panel).to_have_attribute("data-item-id666", "702")
            expect(panel.locator('[data-target666="sets"]')).to_have_text("4")
            expect(panel.locator('[data-target666="weight"]')).to_have_text("70 lb")
            page.goto("https://tracker.test/workouts/quick?machine=52")
            expect(page.locator("#workout666-targets")).to_have_count(0)
            page.goto("https://tracker.test/workouts/quick?machine=50&routine=100")
            expect(page.locator("#workout666-targets")).to_be_visible()
            expect(page.locator("#workout666-target-values")).to_be_hidden()
            page.goto("https://tracker.test/workouts/quick?machine=50&free=1")
            expect(page.locator("#workout666-targets")).to_have_count(0)

            page.goto(URL)
            # Invalid and corrupt plan values never appear as targets.
            page.evaluate("""() => localStorage.setItem(
                'tracker.workout665.plan.routine.99',
                JSON.stringify({version:1, targets:{
                    701:{sets:'21', reps:'9', weight:'-5'}
                }})
            )""")
            page.reload()
            panel = page.locator("#workout666-targets")
            expect(panel.locator('[data-target666="sets"]')).to_have_text("—")
            expect(panel.locator('[data-target666="reps"]')).to_have_text("9")
            expect(panel.locator('[data-target666="weight"]')).to_have_text("—")
            page.evaluate("""() => localStorage.setItem(
                'tracker.workout665.plan.routine.99', '{bad-json'
            )""")
            page.reload()
            expect(page.locator("#workout666-target-values")).to_be_hidden()

            # Clearing the planner's storage in another tab refreshes the UI.
            page.evaluate("""() => localStorage.setItem(
                'tracker.workout665.plan.routine.99',
                JSON.stringify({version:1, targets:{701:{sets:'2'}}})
            )""")
            other = context.new_page()
            other.goto(URL)
            expect(other.locator('[data-target666="sets"]')).to_have_text("2")
            other.evaluate("""() => localStorage.removeItem(
                'tracker.workout665.plan.routine.99'
            )""")
            expect(page.locator("#workout666-target-values")).to_be_hidden()
            other.close()

            assert all(method == "GET" for method, url in requests), requests
            assert not errors, errors
        finally:
            context.close()
            browser.close()
