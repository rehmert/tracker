"""Release 676: Daily Shortcuts visual parity and unchanged navigation behavior."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "app/templates"


def test_676_shared_css_loaded_after_global_mobile_styles():
    base = (T / "base.html").read_text(encoding="utf-8")
    assert "tracker-shortcut-buttons676.css?v=676" not in base
    assert base.count("tracker-ui-foundation679.css?v=742") == 1
    assert base.index("tracker-mobile-ux673.css?v=673") < base.index(
        "tracker-ui-foundation679.css?v=742"
    )
    bundled = (ROOT / "app/static/css/tracker-ui-foundation679.css").read_text()
    assert "#main-content nav.ux675-actions" in bundled
    css = (ROOT / "app/static/css/tracker-shortcut-buttons676.css").read_text()
    daily = (ROOT / "app/static/css/tracker-mobile-daily509.css").read_text()
    for token in ("--surface", "--rule", "--ink", "--teal", "min-height:3.2rem",
                  "border-radius:.85rem", "font-weight:750"):
        assert token in css and token in daily
    assert "#main-content nav.ux675-actions > a" in css
    assert "#main-content nav.ux675-actions > details.ux675-more > summary" in css
    assert "#main-content nav.ux675-actions > details.ux675-more > div > a" in css
    assert "@media (max-width:760px)" in css
    assert "focus-visible" in css
    assert css.count("{") == css.count("}")
    Environment().parse(base)


def test_676_navigation_targets_and_write_forms_stay_unchanged():
    pages = {
        "workouts654.html": ("/workouts/quick", "/workouts/analytics",
                             "/workouts/calendar", "/workouts/backfill"),
        "workout_quick659.html": ("/workouts/quick/sets", "/workouts/quick/finish"),
        "workout_review663.html": ("/export.csv", "/export-for-import.csv", "/correct"),
        "purchases.html": ("#new-purchase", "#purchase-history", "/vendor-prices"),
        "workout_analytics660.html": ("/workouts/quick",),
        "workout_calendar664.html": ("/workouts/quick",),
        "workout_program667.html": ("/workouts/quick",),
    }
    for name, routes in pages.items():
        html = (T / name).read_text(encoding="utf-8")
        assert "ux675-actions" in html
        for route in routes:
            assert route in html, (name, route)
        Environment().parse(html)
    home = (T / "workouts654.html").read_text()
    assert 'action="/workouts/sets"' in home
    assert 'action="/workouts/finish"' in home
    assert '<nav class="ux675-actions"' in home
    assert "<button><a " not in home
