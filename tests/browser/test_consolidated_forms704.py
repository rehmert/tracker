"""Release 704: real Jinja editors with synthetic populated/invalid-state data.

The original forms are rendered, not copied or cloned; no server, installed
records, outbound HTTP, or write requests are used. All Save submits are
intercepted before a navigation. 90 width/density/theme combinations.
"""
from pathlib import Path
from types import SimpleNamespace
import os

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "app/templates"
A = ROOT / "app/static"
SHELL = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head><body><div id="app-shell">
<button type="button" id="sidebar-open" hidden>Menu</button>
<main id="main-content">{% block content %}{% endblock %}</main>
<nav class="tracker-mobile-dock" aria-label="Mobile navigation">
<a href="/mobile">Today</a>
<button id="tracker-mobile-more" type="button">More</button>
</nav></div></body></html>"""
BASE_CSS = """
:root { --surface:#fff; --ink:#192c31; --rule:#cbd5e1;
--teal:#1265ad; --teal-ink:#fff; --wash:#f1f5f9; }
body { margin:0; font:16px/1.5 system-ui,sans-serif; }
#main-content { box-sizing:border-box; max-width:960px; margin:0 auto; padding:12px; }
#main-content :is(input:not([type="checkbox"]),select,textarea) {
  box-sizing:border-box; max-width:100%; min-height:44px;
}
#main-content .grid { display:grid; grid-template-columns:minmax(0,1fr); gap:.5rem; }
#main-content .field { display:grid; gap:.3rem; min-width:0; }
#main-content form { min-width:0; }
"""
STYLES = (
    A / "app.css",
    A / "css/tracker-mobile-shell507.css",
    A / "css/tracker-mobile-density600.css",
    A / "css/tracker-mobile-ux673.css",
    A / "css/tracker-consolidated-forms704.css",
)
MOBILE_JS = (A / "js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
LAB_STICKY_JS = (A / "js/tracker-lab-sticky-actions704.js").read_text(encoding="utf-8")
DENSITIES = ("compact", "balanced", "comfortable")
SCHEMES = ("light", "dark")
WIDTHS = (320, 390, 430, 760, 1024)


def render(kind: str, error: bool = False) -> str:
    env = Environment(
        loader=ChoiceLoader([DictLoader({"base.html": SHELL}), FileSystemLoader(str(T))]),
        autoescape=True,
    )
    env.filters["dt"] = str
    if kind == "notes":
        return env.get_template("page_edit.html").render(
            p=None, title="Example Note", compounds=[], selected=[],
        )
    if kind == "workout":
        return env.get_template("workout_backfill658.html").render(
            equipment=[SimpleNamespace(id=3, name="Leg Press", gym="Sample Gym")],
            routines=[],
            values=SimpleNamespace(today="2026-11-19", day="2026-11-18",
                                   start_time="10:00", end_time="10:45", routine_id=""),
            form_rows=[SimpleNamespace(equipment_id="3", weight_lb="150",
                                       reps="12", effort="7", set_time="10:20")],
            max_rows=24,
            error="Correct the example set before saving." if error else None,
        )
    return env.get_template("lab_form.html").render(
        source_reports=[], copied_from=None,
        v=SimpleNamespace(drawn_on="2026-11-19", lab_name="Example Lab",
                          notes="Example notes"),
        rows=[dict(analyte="TSH",value="1.0",unit="mIU/L",
                   ref_low="0.4",ref_high="4.0",note="")],
        names=["TSH", "Free T4"],
    )


@pytest.mark.parametrize("kind", ("notes", "workout", "lab"))
@pytest.mark.parametrize("width", WIDTHS)
def test_704_mobile_long_form_actions_and_original_submit_contract(kind, width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844},
                                    reduced_motion="reduce")
            errors, writes = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: writes.append((r.method, r.url))
                    if r.method.upper() != "GET" else None)
            page.route("**/*", lambda route: route.abort())
            page.set_content(render(kind, error=kind == "workout"))
            page.add_style_tag(content=BASE_CSS)
            for stylesheet in STYLES:
                page.add_style_tag(content=stylesheet.read_text(encoding="utf-8"))
            if kind == "workout":
                page.add_style_tag(content=(
                    A / "css/tracker-workouts658.css"
                ).read_text(encoding="utf-8"))
            page.add_script_tag(content=MOBILE_JS)
            if kind == "lab":
                page.add_script_tag(content=LAB_STICKY_JS)

            if kind == "notes":
                form = page.locator('form[action="/pages"]')
                assert form.count() == 1
                assert form.locator("#notes-discard-draft").count() == 1
                assert form.locator('textarea[name="body"]').count() == 1
                expected = ("title", "body")
            elif kind == "workout":
                form = page.locator("#workout658-form")
                assert form.count() == 1
                assert form.locator('select[name="equipment_id"]').count() == 1
                assert page.locator('[role="alert"]').count() == 1
                assert page.locator('form[action="/workouts/backfill/import.csv"]').count() == 1
                expected = ("day", "equipment_id", "reps")
            else:
                form = page.locator("form[data-lab-manual-entry]")
                assert form.count() == 1
                assert page.locator('form[data-lab-csv-entry]').count() == 1
                assert form.locator('button[hx-get="/labs/row"]').count() == 1
                assert form.locator("#lab-rows").count() == 1
                expected = ("drawn_on", "lab_name")
            row = form.locator(".tracker-form-actions704")
            save = row.locator("button.primary")
            cancel = row.locator("a.btn")
            dock = page.locator(".tracker-mobile-dock")
            assert row.count() == save.count() == cancel.count() == 1
            assert form.get_attribute("method") == "post"
            assert row.evaluate("el => el.closest('form')?.getAttribute('method')") == "post"
            if kind == "notes":
                assert form.get_attribute("action") == "/pages"
                assert cancel.get_attribute("href") == "/pages"
            if kind == "workout":
                assert form.get_attribute("action") == "/workouts/backfill"
                assert cancel.get_attribute("href") == "/workouts"
            if kind == "lab":
                assert form.get_attribute("action") == "/labs"
                assert cancel.get_attribute("href") == "/labs"

            # Ensure a genuinely long page even with one synthetic row.
            row.evaluate("""el => {
                const spacer = document.createElement('div');
                spacer.style.height = '950px';
                spacer.style.gridColumn = '1 / -1';
                spacer.dataset.test704Spacer = '';
                el.before(spacer);
            }""")

            for density in DENSITIES:
                for scheme in SCHEMES:
                    page.evaluate("""([density,scheme]) => {
                        document.documentElement.dataset.density=density;
                        document.documentElement.dataset.theme=scheme;
                    }""", [density,scheme])
                    page.evaluate("window.scrollTo(0,0)")
                    if width <= 760:
                        expect(dock).to_be_visible()
                        expect(row).to_be_visible()
                        if kind == "lab":
                            # At the top of the page, the CSV form precedes
                            # the manual form. The latter can start within
                            # the dock's region in Comfortable density.
                            # Require the original action row to stay in
                            # natural flow until the manual form reaches the
                            # genuinely safe sticky region.
                            safe_at_top = page.evaluate("""() => {
                                const form = document.querySelector(
                                    "form[data-lab-manual-entry]"
                                );
                                const bar = form.querySelector(
                                    ":scope > .tracker-form-actions704--lab"
                                );
                                const dock = document.querySelector(
                                    ".tracker-mobile-dock"
                                );
                                return form.getBoundingClientRect().top +
                                    bar.getBoundingClientRect().height + 16 <=
                                    dock.getBoundingClientRect().top;
                            }""")
                            page.wait_for_function("""expected =>
                                document.querySelector("form[data-lab-manual-entry]")
                                  .classList.contains("tracker-lab-actions704-active")
                                  === expected
                            """, arg=safe_at_top)
                            if not safe_at_top:
                                assert row.evaluate(
                                    "el=>getComputedStyle(el).position"
                                ) == "static"
                                offscreen = row.bounding_box()
                                nav_initial = dock.bounding_box()
                                assert offscreen and nav_initial
                                assert (offscreen["y"] >=
                                        nav_initial["y"] + nav_initial["height"]) or (
                                    offscreen["y"] + offscreen["height"] <=
                                    nav_initial["y"] - 4
                                ), (kind, width, density, scheme,
                                    "nonsticky_must_not_cover_dock", offscreen, nav_initial)
                            # Enter the manual form. The original actions
                            # must then activate without crossing the dock.
                            page.evaluate("""() => {
                                const form = document.querySelector(
                                    "form[data-lab-manual-entry]"
                                );
                                window.scrollTo(
                                    0, window.scrollY +
                                    form.getBoundingClientRect().top - 120
                                );
                            }""")
                            page.wait_for_function("""() =>
                                document.querySelector("form[data-lab-manual-entry]")
                                  .classList.contains("tracker-lab-actions704-active")
                            """)
                        assert row.evaluate("el=>getComputedStyle(el).position") == "sticky"
                        controls = [save, cancel]
                        if kind == "lab":
                            add_row = row.locator('button[type="button"][hx-get="/labs/row"]')
                            controls.insert(0, add_row)
                            assert row.evaluate("""el =>
                                getComputedStyle(el).gridTemplateColumns.split(' ').length
                            """) == 3
                        boxes = []
                        for el in controls:
                            box = el.bounding_box()
                            assert box and box["height"] >= 44, (
                                kind, width, density, scheme, box
                            )
                            boxes.append(box)
                        if kind == "lab":
                            # Add row / Save / Cancel should share one compact
                            # row, not force a tall second row behind the dock.
                            assert abs(boxes[0]["y"] - boxes[1]["y"]) <= 2
                            assert abs(boxes[1]["y"] - boxes[2]["y"]) <= 2
                            assert boxes[0]["x"] < boxes[1]["x"] < boxes[2]["x"]
                        action = row.bounding_box()
                        nav = dock.bounding_box()
                        assert action and nav
                        assert action["y"] >= -1
                        clearance = nav["y"] - (action["y"] + action["height"])
                        if clearance < 4:
                            diagnostics = row.evaluate("""el => {
                                const chain = [];
                                for (let n = el; n && chain.length < 7; n = n.parentElement) {
                                    const s = getComputedStyle(n), r = n.getBoundingClientRect();
                                    chain.push({
                                        tag: n.tagName, className: String(n.className).slice(0,90),
                                        position: s.position, bottom: s.bottom,
                                        overflowX: s.overflowX, overflowY: s.overflowY,
                                        top: Math.round(r.top), height: Math.round(r.height),
                                        scrollTop: n.scrollTop
                                    });
                                }
                                return {
                                    viewport: innerHeight, windowY: scrollY,
                                    documentHeight: document.documentElement.scrollHeight, chain
                                };
                            }""")
                            raise AssertionError(
                                (kind, width, density, scheme, action, nav,
                                 "dock_clearance", clearance, diagnostics)
                            )
                    else:
                        expect(dock).to_be_hidden()
                        assert row.evaluate("el=>getComputedStyle(el).position") == "static"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth + 1"
                    ), (kind,width,density,scheme)
                    if width <= 760:
                        field = form.locator('input[name="title"]') if kind == "notes" \
                            else form.locator('input[name="weight_lb"]').first if kind == "workout" \
                            else form.locator('input[name="lab_name"]')
                        field.focus()
                        expect(dock).to_be_hidden()
                        assert row.evaluate("el=>getComputedStyle(el).position") == "static"
                        field.evaluate("el=>el.blur()")
                        page.wait_for_function("""() =>
                            !document.documentElement.classList.contains('tracker-mobile-editing')
                        """)
                        expect(dock).to_be_visible()
                        assert row.evaluate("el=>getComputedStyle(el).position") == "sticky"

            # Confirm one native submit without posting any data.
            form.evaluate("""el => {
                window.__submits704=0;
                el.addEventListener('submit', event => {
                    event.preventDefault();
                    window.__submits704 += 1;
                    window.__fields704 = [...new FormData(el).keys()];
                });
            }""")
            save.focus()
            page.keyboard.press("Tab")
            if kind == "notes":
                expect(row.locator("#notes-discard-draft")).to_be_focused()
            else:
                expect(cancel).to_be_focused()
            save.click()
            assert page.evaluate("window.__submits704") == 1
            assert page.evaluate(
                "names=>names.every(name=>window.__fields704.includes(name))",
                list(expected),
            )
            assert not writes, writes
            assert not errors, errors
        finally:
            browser.close()


def test_704_lab_manual_invalid_date_does_not_submit():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(render("lab"))
            form = page.locator("form[data-lab-manual-entry]")
            form.locator('input[name="drawn_on"]').fill("")
            assert not form.evaluate("el=>el.checkValidity()")
            form.evaluate("""el => {
                window.__invalidSubmits704=0;
                el.addEventListener('submit', event => {
                  event.preventDefault(); window.__invalidSubmits704++;
                });
            }""")
            form.locator(".tracker-form-actions704 button.primary").click()
            assert page.evaluate("window.__invalidSubmits704") == 0
        finally:
            browser.close()
