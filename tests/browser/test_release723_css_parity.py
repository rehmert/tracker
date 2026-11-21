"""Release 723: actual browser screenshot and computed-style parity across Gym CSS merge."""
from pathlib import Path
import subprocess

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "app/static/css"
BASE = "40088e446b66285aaa07caf40566e4de80864a98"


def old(path):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT),
         "show", f"{BASE}:app/static/css/{path}"], text=True
    )


HTML = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style id="gym-rules"></style></head><body>
<main id="main-content"><section class="workout659" id="workout659-root">
<nav class="ux675-actions ux675-gym-top"><a href="#top">Workouts</a><a href="#progress">Progress</a>
<details class="ux675-more"><summary>More</summary><div><a href="#insights">Insights</a></div></details></nav>
<section class="workout659-panel">
<form class="workout659-machine-picker"><label for="machine">Current machine</label>
<div class="workout659-picker-row"><select id="machine"><option>Nautilus Row</option></select><button>Go</button></div></form>
<details class="workout662-directory"><summary>Find Machine</summary><input value="" placeholder="Search machine">
<nav class="workout662-directory-list"><a href="#one">Nautilus Chest Press</a></nav></details>
<div class="workout659-prior"><strong>95 lb × 10 reps</strong></div>
<aside class="workout667-active-goal"><p>3 working sets</p><button id="workout667-use-goal">Use planned weight &amp; reps</button></aside>
<div class="workout659-number-grid">
<div class="workout659-number-control"><label>Weight (lb)</label>
<div class="workout659-stepper"><button>-5</button><input value="95"><button>+5</button></div></div>
<div class="workout659-number-control"><label>Repetitions</label>
<div class="workout659-stepper"><button>-1</button><input value="10"><button>+1</button></div></div></div>
<button class="workout659-main-button">Save Set</button>
<div class="workout662-adjustments"><button>-2.5 lb</button><button>+2.5 lb</button><button>-5 reps</button><button>+5 reps</button></div>
<nav class="workout662-nav"><a class="workout662-next" href="#next">Next Machine: Nautilus Chest Press</a></nav>
<details class="ux673-gym-offline"><summary>Offline &amp; Draft Tools</summary>
<div class="ux673-gym-offline-content"><button>Save Local Draft</button></div></details>
</section></section></main></body></html>"""

SELECTORS = (
    ".workout659-panel", ".workout659-machine-picker", ".workout662-directory",
    ".workout659-number-grid", ".workout659-stepper button", ".workout659-main-button",
    ".workout662-adjustments", ".workout662-nav a", ".workout667-active-goal",
    ".ux673-gym-offline > summary", ".ux675-gym-top > a",
)
PROPS = ("display", "height", "minHeight", "padding", "margin", "width",
         "gap", "color", "backgroundColor", "borderRadius", "fontSize")


@pytest.mark.browser
def test_723_gym_css_screenshot_and_style_parity():
    old_css = "\n".join((
        old("tracker-workouts659.css"),
        old("tracker-workouts662.css"),
        old("tracker-workout-targets666.css"),
        old("tracker-workout-gym667.css"),
        old("tracker-workout-ux673.css"),
        old("tracker-action-nav675.css"),
        old("tracker-integrated-flow696.css"),
        old("tracker-workouts716.css"),
    ))
    merged_css = "\n".join(
        (CSS / x).read_text(encoding="utf-8") for x in (
            "tracker-workouts659.css", "tracker-workout-targets666.css",
            "tracker-workout-gym667.css", "tracker-action-nav675.css",
            "tracker-integrated-flow696.css", "tracker-workouts716.css",
        )
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in (320, 390, 430, 760, 1024):
                for scheme in ("light", "dark"):
                    for density in ("compact", "balanced", "comfortable"):
                        page = browser.new_page(
                            viewport={"width": width, "height": 844},
                            color_scheme=scheme,
                        )
                        try:
                            page.set_content(HTML)
                            page.evaluate(
                                "(d) => document.documentElement.dataset.density = d",
                                density,
                            )
                            theme = (
                                ":root{--surface:#fff;--ink:#182c37;--border:#879eae;--rule:#879eae;--teal:#1265ad}"
                                if scheme == "light" else
                                ":root{--surface:#17252e;--ink:#ecf2f8;--border:#7e9bac;--rule:#7e9bac;--teal:#78baff}"
                            )
                            def render(css):
                                page.locator("#gym-rules").evaluate(
                                    "(el, value) => el.textContent = value", theme + css
                                )
                                return (
                                    page.screenshot(full_page=True),
                                    page.evaluate("""([selectors, props]) => selectors.map(
                                      selector => {
                                        const style = getComputedStyle(document.querySelector(selector));
                                        return props.map(p => style[p]);
                                      }
                                    )""", [list(SELECTORS), list(PROPS)]),
                                    page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
                                )
                            before = render(old_css)
                            after = render(merged_css)
                            assert before == after, (width, scheme, density)
                            assert after[2], (width, scheme, density)
                            assert page.locator(".workout659-main-button").evaluate(
                                "el => el.getBoundingClientRect().height >= 48"
                            )
                        finally:
                            page.close()
        finally:
            browser.close()
