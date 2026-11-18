"""Release 678: actual Overview Workout Activity fragment renders as shortcut cards."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "app/templates/_workout_dashboard661.html"
DASHBOARD = ROOT / "app/templates/dashboard.html"
CSS = ROOT / "app/static/css/tracker-workout-dashboard661.css"


def test_678_workout_activity_links_are_card_actions_not_bare_link_boxes():
    src = FRAGMENT.read_text(encoding="utf-8")
    assert 'class="tracker-workout-actions661 tracker-workout-shortcuts678"' in src
    assert 'class="tracker-workout-primary678"' in src
    assert 'class="tracker-workout-empty-action678"' in src
    for url in (
        '/workouts/quick', '/workouts/analytics', '/workouts/insights',
        '/workouts/routines', '/workouts/calendar', '/workouts',
        '/workouts/backfill',
    ):
        assert f'href="{url}"' in src
    assert src.count('<a href="/workouts/') == 1  # recent session date is dynamic
    assert src.count('<a ') == 8  # six nav actions + recent session + backfill
    assert src.count('<strong>') >= 5
    assert "data-dashboard-panel=\"9\"" in src
    Environment().parse(src)


def test_678_dashboard_loads_fresh_scoped_stylesheet_and_matches_daily_cards():
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert 'tracker-workout-dashboard661.css?v=678' in dashboard
    assert dashboard.count("tracker-workout-dashboard661.css?v=") == 1
    assert "#tracker-workout-dashboard661 nav.tracker-workout-shortcuts678 > a" in css
    assert "text-decoration:none;" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "grid-template-columns:minmax(0,1fr)" in css
    for rule in ("--border", "--surface", "border-radius:9px",
                 "min-height:3.25rem", "font-size:.95rem"):
        assert rule in css
    Environment().parse(dashboard)
