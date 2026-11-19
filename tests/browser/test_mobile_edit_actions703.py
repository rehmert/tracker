"""Release 703: two actual Jinja edit templates rendered with synthetic data.

No installed database, app server or network. All Save events are intercepted
before navigation; the Vitals original dirty/restore guard runs unchanged.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "app/templates"
ASSETS = ROOT / "app/static"
SHELL = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head><body><div id="app-shell">
<button type="button" id="sidebar-open" hidden>Menu</button>
<main id="main-content">{% block content %}{% endblock %}</main>
<nav class="tracker-mobile-dock" aria-label="Mobile quick navigation">
<a href="/mobile">Today</a>
<button id="tracker-mobile-more" type="button">More</button>
</nav></div></body></html>"""
BASE_CSS = """
:root{--surface:#fff;--ink:#192c31;--rule:#cbd5e1;
--teal:#1265ad;--teal-ink:#fff;--wash:#f1f5f9}
body{margin:0;font:16px/1.5 system-ui,sans-serif}
#main-content{box-sizing:border-box;max-width:920px;margin:0 auto;padding:12px}
#main-content form.grid{display:grid;grid-template-columns:minmax(0,1fr);gap:.7rem}
#main-content form label{display:grid;gap:.15rem;min-width:0}
#main-content form :is(input,select,textarea){min-height:44px;
  box-sizing:border-box;max-width:100%;width:100%;padding:.45rem}
@media (min-width:761px){
 #main-content form.grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
"""
STYLES = (
    ASSETS / "app.css",
    ASSETS / "css/tracker-mobile-shell507.css",
    ASSETS / "css/tracker-mobile-density600.css",
    ASSETS / "css/tracker-mobile-ux673.css",
    ASSETS / "css/tracker-vitals-edit-guard.css",
    ASSETS / "css/tracker-mobile-edit-actions703.css",
)
MOBILE_JS = (ASSETS / "js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
GUARD_JS = (ASSETS / "js/tracker-vitals-edit-guard.js").read_text(encoding="utf-8")
WIDTHS = (320, 390, 430, 760, 1024)
DENSITIES = ("compact", "balanced", "comfortable")
SCHEMES = ("light", "dark")


def render_editor(kind: str, locked: bool = False) -> str:
    env = Environment(loader=DictLoader({
        "base.html": SHELL,
        "vitals_edit.html": (TPL / "vitals_edit.html").read_text(encoding="utf-8"),
        "compound_edit.html": (TPL / "compound_edit.html").read_text(encoding="utf-8"),
    }), autoescape=True)
    if kind == "vitals":
        reading = SimpleNamespace(
            id=42, systolic=120, diastolic=75, pulse_bpm=76,
            context="Morning", notes="Original entry",
        )
        return env.get_template("vitals_edit.html").render(
            reading=reading, days=30, events=1,
            measured_at="2026-11-19T08:30", weight="265", unit="lb",
        )
    compound = SimpleNamespace(
        id=17, name="Example compound", category="peptide",
        primary_unit="mg", notes="Original notes",
    )
    return env.get_template("compound_edit.html").render(
        compound=compound, categories=("peptide", "other"),
        units=("mg", "IU"), has_vials=locked,
    )


@pytest.mark.parametrize("kind", ("vitals", "compound"))
@pytest.mark.parametrize("width", WIDTHS)
def test_703_original_save_cancel_responsive_layout_and_original_guard(kind, width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                reduced_motion="reduce",
            )
            page.on("dialog", lambda dialog: dialog.dismiss())
            errors = []
            writes = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.on("request", lambda request: writes.append(
                (request.method, request.url)
            ) if request.method.upper() != "GET" else None)
            page.route("**/*", lambda route: route.abort())
            page.set_content(render_editor(kind))
            page.add_style_tag(content=BASE_CSS)
            for stylesheet in STYLES:
                page.add_style_tag(content=stylesheet.read_text(encoding="utf-8"))
            page.add_script_tag(content=MOBILE_JS)
            if kind == "vitals":
                page.add_script_tag(content=GUARD_JS)

            form = page.locator("form[method=post]")
            row = page.locator(".tracker-mobile-edit-actions703")
            save = row.locator('button[type="submit"]')
            cancel = row.locator("a")
            dock = page.locator(".tracker-mobile-dock")
            assert form.count() == row.count() == save.count() == cancel.count() == 1
            assert row.evaluate("el => el.closest('form') === document.querySelector('form[method=post]')")
            if kind == "vitals":
                assert form.get_attribute("action") == "/vitals/42/edit"
                assert cancel.get_attribute("href") == "/vitals?days=30&events=1"
                assert cancel.get_attribute("data-vitals-edit-cancel") is not None
                assert form.locator('input[name="days"]').input_value() == "30"
                assert form.locator('input[name="events"]').input_value() == "1"
                expect(row.locator(".tracker-vitals-restore")).to_have_count(1)
                expect(row.locator(".tracker-vitals-dirty-status")).to_have_text(
                    "No Unsaved Changes"
                )
                expect(row.locator(".tracker-vitals-restore")).to_be_disabled()
            else:
                assert form.get_attribute("action") == "/compounds/17/edit"
                assert cancel.get_attribute("href") == "/compounds"
                assert row.locator("button").count() == 1

            # Add a synthetic long-scroll gap to the real template fixture,
            # making the bottom-sticky rule observable even for short forms.
            row.evaluate("""el => {
                const spacer = document.createElement('div');
                spacer.style.height = '950px';
                spacer.style.gridColumn = '1 / -1';
                spacer.dataset.preview703Spacer = '';
                el.before(spacer);
            }""")
            for density in DENSITIES:
                for scheme in SCHEMES:
                    page.evaluate("""([density,scheme]) => {
                        document.documentElement.dataset.density=density;
                        document.documentElement.dataset.theme=scheme;
                    }""", [density, scheme])
                    page.evaluate("() => window.scrollTo(0,0)")
                    if width <= 760:
                        expect(dock).to_be_visible()
                        expect(row).to_be_visible()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "sticky"
                        assert row.evaluate(
                            "el => getComputedStyle(el).gridColumnStart"
                        ) in ("1", "1 / -1")
                        for control in (save, cancel):
                            box = control.bounding_box()
                            assert box is not None and box["height"] >= 44, (
                                kind, width, density, scheme, box
                            )
                        row_box = row.bounding_box()
                        dock_box = dock.bounding_box()
                        assert row_box is not None and dock_box is not None
                        assert row_box["y"] >= -1
                        assert row_box["y"] + row_box["height"] <= dock_box["y"] - 4, (
                            kind, width, density, scheme, row_box, dock_box
                        )
                        if kind == "vitals":
                            expect(row.locator(".tracker-vitals-restore")).to_be_visible()
                            expect(row.locator(".tracker-vitals-dirty-status")).to_be_visible()
                    else:
                        expect(dock).to_be_hidden()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "static"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth + 1"
                    ), (kind, width, density, scheme)

                    if width <= 760:
                        edit = form.locator('input[name="weight"]') if kind == "vitals" \
                            else form.locator('input[name="name"]')
                        edit.focus()
                        expect(dock).to_be_hidden()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "static"
                        edit.evaluate("el => el.blur()")
                        page.wait_for_function("""() =>
                            !document.documentElement.classList.contains('tracker-mobile-editing')
                        """)
                        expect(dock).to_be_visible()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "sticky"

            if kind == "vitals":
                input_name = form.locator('input[name="weight"]')
                input_name.fill("264")
                expect(row.locator(".tracker-vitals-dirty-status")).to_have_text(
                    "Unsaved Changes"
                )
                restore = row.locator(".tracker-vitals-restore")
                expect(restore).to_be_enabled()
                restore.click()
                expect(input_name).to_have_value("265")
                expect(row.locator(".tracker-vitals-dirty-status")).to_have_text(
                    "No Unsaved Changes"
                )

                # The original unsaved-changes Cancel interception still
                # fires. Dismiss the confirmation: no navigation is allowed.
                input_name.fill("263")
                page.evaluate("""() => {
                    window.__discardPrompts703 = [];
                    window.confirm = msg => {
                        window.__discardPrompts703.push(msg);
                        return false;
                    };
                }""")
                cancel.click()
                assert page.evaluate(
                    "window.__discardPrompts703.length"
                ) == 1
                assert "Discard unsaved changes" in page.evaluate(
                    "window.__discardPrompts703[0]"
                )
                expect(input_name).to_have_value("263")
                restore.click()
                expect(input_name).to_have_value("265")
            # Save sends one native form submit without duplicate control or
            # network request. Prevent default (no real mutation/redirect).
            form.evaluate("""form => {
                window.__saveAttempts703 = 0;
                form.addEventListener('submit', event => {
                    event.preventDefault();
                    window.__saveAttempts703++;
                    window.__keys703 = [...new FormData(form).keys()];
                });
            }""")
            save.focus()
            page.keyboard.press("Tab")
            expect(cancel).to_be_focused()
            save.click()
            assert page.evaluate("window.__saveAttempts703") == 1
            names = ("days", "events", "measured_at") if kind == "vitals" \
                else ("name", "category", "primary_unit")
            assert page.evaluate(
                "names => names.every(n => window.__keys703.includes(n))",
                list(names),
            )
            assert not writes, writes
            assert not errors, errors
        finally:
            browser.close()


def test_703_compound_with_vials_keeps_original_hidden_locked_unit():
    html = render_editor("compound", locked=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page()
            page.set_content(html)
            control = page.locator('select[name="primary_unit"]')
            expect(control).to_be_disabled()
            assert page.locator('input[type="hidden"][name="primary_unit"]').input_value() == "mg"
            assert page.locator(".tracker-mobile-edit-actions703 button[type=submit]").count() == 1
        finally:
            browser.close()
