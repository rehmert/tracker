"""Release 725: Rest Timer is not buried below optional Gym tools."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/templates/workout_quick659.html"
TOOLS = ROOT / "app/templates/_workout_quick_tools722.html"


def test_725_rest_timer_below_logging_and_above_optional_tools():
    html = MAIN.read_text(encoding="utf-8")
    Environment().parse(html)
    markers = (
        'id="workout659-save"',
        'class="workout659-panel workout659-rest-panel"',
        '<summary>Load Setup</summary>',
        'Offline &amp; Draft Tools',
        '{% include "_workout_quick_tools722.html" %}',
        'Planned Training Groups',
    )
    positions = [html.rindex(x) if x.startswith('{% include') else
                 html.index(x) for x in markers]
    assert positions == sorted(positions)
    for identifier in ("workout659-rest-start", "workout659-rest-reset",
                       "workout659-rest-display", "workout659-rest-duration",
                       "workout668-sync-status", "workout659-log-form"):
        assert html.count(f'id="{identifier}"') == 1
    assert html.count('class="workout662-nav"') == 1
    assert html.count('{% include "_workout_quick_tools722.html" %}') == 2
    assert 'workout659-move' not in html
    Environment().parse(TOOLS.read_text())


def test_725_timer_js_and_signed_post_forms_are_unchanged():
    html = MAIN.read_text(encoding="utf-8")
    for action in ("/workouts/quick/sets", "/workouts/quick/repeat",
                   "/workouts/quick/finish"):
        assert html.count(f'action="{action}"') == 1
    assert html.count('formaction="/workouts/finish-review"') == 1
    assert 'id="workout659-rest-status"' in html
    js = (ROOT / "app/static/js/tracker-workouts659.js").read_text()
    for marker in ("workout659-rest-display", "workout659-rest-start",
                   "workout659-rest-duration", "workout659-rest-reset"):
        assert marker in js
