"""Release 721: native disclosure has a visible, stateful chevron."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def test_721_recent_workouts_chevron_contract():
    css = (ROOT / "app/static/css/tracker-workout-dashboard661.css").read_text()
    fragment = (ROOT / "app/templates/_workout_dashboard661.html").read_text()
    dashboard = (ROOT / "app/templates/dashboard.html").read_text()
    assert '<details class="tracker-workout-recent661"' in fragment
    assert '<summary>Recent Workouts</summary>' in fragment
    assert '{% if workout_summary.recent_expanded %}open{% endif %}' in fragment
    assert "tracker-workout-dashboard661.css?v=721" in dashboard
    assert (
        ".tracker-workout-recent661 > summary::after" in css
        and r'content:"\25BE"' in css
    )
    assert ".tracker-workout-recent661[open] > summary::after" in css
    assert "transform:rotate(180deg)" in css
    assert "min-height:48px" in css
    Environment().parse(fragment)
