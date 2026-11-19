"""Release 704: real five-editor Jinja forms and local Chromium, synthetic data only.

No app server, user records, outgoing network, or form write requests.
Tests deliberately leave original route/UI logic in place while exercising
the shared mobile action treatment and native-invalid accessibility message.
"""
from datetime import datetime
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "app/templates"
STATIC = ROOT / "app/static"
KINDS = ("dose", "notes", "workout", "preparation", "lab")
WIDTHS = (320, 390, 430, 760, 1024)
DENSITIES = ("compact", "balanced", "comfortable")
THEMES = ("light", "dark")
TEMPLATES = {
    "dose": "dose_edit.html",
    "notes": "page_edit.html",
    "workout": "workout_backfill658.html",
    "preparation": "preparation_edit.html",
    "lab": "lab_form.html",
}
SHELL = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
{% block page_assets %}{% endblock %}
</head><body><div id="app-shell">
<button type="button" id="sidebar-open" hidden>Menu</button>
<main id="main-content">{% block content %}{% endblock %}</main>
<nav class="tracker-mobile-dock" aria-label="Mobile navigation">
<a href="/mobile">Today</a>
<button id="tracker-mobile-more" type="button">More</button>
</nav></div></body></html>"""
BASE_CSS = """
:root{--surface:#fff;--ink:#192c31;--rule:#cbd5e1;
--teal:#1265ad;--teal-ink:#fff;--wash:#f1f5f9}
body{margin:0;font:16px/1.5 system-ui,sans-serif}
#main-content{box-sizing:border-box;max-width:950px;margin:0 auto;padding:12px}
#main-content form.grid{display:grid;
grid-template-columns:repeat(auto-fit,minmax(min(100%,13rem),1fr));gap:.6rem}
#main-content form label{display:flex;flex-direction:column;gap:.2rem;min-width:0}
#main-content form :is(input,select,textarea){box-sizing:border-box;max-width:100%}
"""
CSS = (
    STATIC / "app.css",
    STATIC / "css/tracker-mobile-shell507.css",
    STATIC / "css/tracker-mobile-density600.css",
    STATIC / "css/tracker-mobile-ux673.css",
    STATIC / "css/tracker-form-overlap586.css",
    STATIC / "css/tracker-workouts658.css",
    STATIC / "css/tracker-edit-actions704.css",
)
MOBILE_JS = (STATIC / "js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
FEEDBACK_JS = (STATIC / "js/tracker-edit-feedback704.js").read_text(encoding="utf-8")


def fake_editor(kind):
    env = Environment(loader=DictLoader({
        "base.html": SHELL,
        **{name: (TEMPLATE_DIR / name).read_text(encoding="utf-8")
           for name in TEMPLATES.values()},
    }), autoescape=True)
    env.filters["num"] = str
    env.filters["utc_dt"] = str
    env.filters["from_json"] = lambda s: {}
    now = datetime(2026, 11, 18, 9, 30)
    if kind == "dose":
        dose = SimpleNamespace(
            id=19, vial_id=8,
            vial=SimpleNamespace(compound=SimpleNamespace(name="Example")),
            taken_at=now, entered_value="2", entered_unit="mg",
            kind="dose", site="", notes="Existing",
        )
        kwargs = dict(
            dose=dose, correction_vials=[
                SimpleNamespace(vial=SimpleNamespace(id=8,label="A",
                    lot="Lot 1",status="in_use"),remaining=10)
            ], DOSE_UNITS=("mg","IU"), sites=("arm","leg"),
            used={}, supplies=[], counted_supply_kinds=set(), history=[],
        )
    elif kind == "notes":
        kwargs = dict(p=None, title="Example page", compounds=[], selected=set())
    elif kind == "workout":
        kwargs = dict(
            equipment=[SimpleNamespace(id=7,name="Example Nautilus",gym="Demo")],
            error=None, routines=[], max_rows=40,
            values=SimpleNamespace(
                today="2026-11-19",day="2026-11-18",
                start_time="09:00",end_time="10:00",routine_id="",
            ),
            form_rows=[
                SimpleNamespace(
                    equipment_id="7",weight_lb="80",reps="10",
                    effort="7",set_time="09:30",
                ),
            ],
        )
    elif kind == "preparation":
        kwargs = dict(
            event=SimpleNamespace(kind="reconstituted",id=4,
                                  occurred_at=now,notes="Original"),
            vial=SimpleNamespace(
                id=12,compound=SimpleNamespace(name="Example")
            ), supplies=[], used={},
        )
    else:
        kwargs = dict(
            source_reports=[],copied_from=None,
            v=SimpleNamespace(
                drawn_on="2026-11-18",lab_name="Example",notes=""
            ),rows=[],names=[],
        )
    return env.get_template(TEMPLATES[kind]).render(**kwargs)


@pytest.mark.parametrize("kind", KINDS)
def test_704_real_jinja_fixture_has_one_original_edit_actions_group(kind):
    html = fake_editor(kind)
    assert html.count('class="tracker-edit-feedback704"') == 1
    assert html.count("tracker-edit-actions704\"") == 1
    assert "role=\"alert\" hidden" in html
    assert "Cancel</a>" in html or "Cancel\n" in html


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_704_editor_accessibility_dock_keyboard_and_native_save(kind, width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(
                viewport={"width":width,"height":844},
                reduced_motion="reduce",
            )
            errors, writes = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: writes.append((r.method,r.url))
                    if r.method.upper() != "GET" else None)
            page.route("**/*", lambda route: route.abort())
            page.set_content(fake_editor(kind))
            page.add_style_tag(content=BASE_CSS)
            for css in CSS:
                page.add_style_tag(content=css.read_text(encoding="utf-8"))
            page.add_script_tag(content=MOBILE_JS)
            page.add_script_tag(content=FEEDBACK_JS)

            action = page.locator(".tracker-edit-actions704")
            form = action.locator("xpath=ancestor::form[1]")
            submit = action.locator('button:not([type="button"])')
            cancel = action.locator("a")
            notice = form.locator(".tracker-edit-feedback704")
            dock = page.locator(".tracker-mobile-dock")
            assert action.count() == form.count() == submit.count() == cancel.count() == notice.count() == 1
            assert action.evaluate(
                "a => a.closest('form') === document.querySelector('form:has(.tracker-edit-actions704)')"
            )
            assert form.get_attribute("method").lower() == "post"
            endpoints = {
                "dose":("/doses/19/edit","/doses"),
                "notes":("/pages","/pages"),
                "workout":("/workouts/backfill","/workouts"),
                "preparation":(None,"/vials/12"),
                "lab":("/labs","/labs"),
            }
            expected_action, expected_cancel = endpoints[kind]
            if expected_action:
                assert form.get_attribute("action") == expected_action
            else:
                assert form.get_attribute("action") is None
            assert cancel.get_attribute("href") == expected_cancel
            if kind == "notes":
                expect(action.locator("#notes-discard-draft")).to_have_count(1)
                assert action.locator('button[type="button"]').count() == 1
            if kind == "workout":
                assert form.locator("#workout658-save").count() == 1
                assert page.locator('form[action="/workouts/backfill/import.csv"]').count() == 1
            if kind == "lab":
                assert page.locator('form[data-lab-csv-entry]').count() == 1
                assert form.get_attribute("data-lab-manual-entry") is not None
                assert form.locator('[hx-get="/labs/row"]').count() == 1

            # Make the sticky state observable for shorter edit forms, too.
            action.evaluate("""a => {
                const spacer = document.createElement('div');
                spacer.style.height='1000px';
                spacer.style.gridColumn='1 / -1';
                a.before(spacer);
            }""")
            for density in DENSITIES:
                for theme in THEMES:
                    page.evaluate("""([d,t])=>{
                        document.documentElement.dataset.density=d;
                        document.documentElement.dataset.theme=t;
                        window.scrollTo(0,0);
                    }""",[density,theme])
                    if width <= 760:
                        expect(dock).to_be_visible()
                        expect(action).to_be_visible()
                        assert action.evaluate(
                            "a => getComputedStyle(a).position"
                        ) == "sticky"
                        for control in (submit,cancel):
                            box=control.bounding_box()
                            assert box and box["height"]>=44,(kind,width,density,theme,box)
                        ab,db=action.bounding_box(),dock.bounding_box()
                        assert ab and db
                        assert ab["y"] >= -1,(kind,width,ab)
                        assert ab["y"]+ab["height"] <= db["y"]-4,(kind,width,ab,db)
                    else:
                        expect(dock).to_be_hidden()
                        assert action.evaluate(
                            "a => getComputedStyle(a).position"
                        ) == "static"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth + 1"
                    ),(kind,width,density,theme)
                    if width<=760:
                        edit=form.locator(
                            'input[name="amount"]' if kind=="dose"
                            else 'input[name="title"]' if kind=="notes"
                            else 'input[name="day"]' if kind=="workout"
                            else 'input[name="occurred_at"]' if kind=="preparation"
                            else 'input[name="drawn_on"]'
                        ).first
                        edit.focus()
                        expect(dock).to_be_hidden()
                        assert action.evaluate(
                            "a => getComputedStyle(a).position"
                        ) == "static"
                        edit.evaluate("a=>a.blur()")
                        page.wait_for_function("""()=>
                            !document.documentElement.classList.contains('tracker-mobile-editing')
                        """)
                        expect(dock).to_be_visible()

            # A native invalid field triggers visible accessible guidance,
            # and normal input hides it once every field is valid.
            required = {
                "dose":('input[name="amount"]',"2"),
                "notes":('input[name="title"]',"Example page"),
                "workout":('input[name="day"]',"2026-11-18"),
                "lab":('input[name="drawn_on"]',"2026-11-18"),
            }
            if kind in required:
                selector, restored = required[kind]
                field = form.locator(selector)
                field.fill("")
                assert form.evaluate("f=>f.checkValidity()") is False
                expect(notice).to_be_visible()
                expect(notice).to_contain_text("Review the highlighted")
                field.fill(restored)
                expect(notice).to_be_hidden()
            else:
                expect(notice).to_be_hidden()

            form.evaluate("""form=>{
                window.__submit704=0;
                form.addEventListener('submit',event=>{
                    event.preventDefault();
                    window.__submit704++;
                    window.__formKeys704=[...new FormData(form).keys()];
                });
            }""")
            submit.focus()
            page.keyboard.press("Tab")
            if kind=="notes":
                expect(action.locator("#notes-discard-draft")).to_be_focused()
                page.keyboard.press("Tab")
            expect(cancel).to_be_focused()
            submit.click()
            assert page.evaluate("window.__submit704") == 1
            assert not writes,writes
            assert not errors,errors
        finally:
            browser.close()
