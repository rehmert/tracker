"""Release 722: active Workout page places logging ahead of secondary tools."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/templates/workout_quick659.html"
TOOLS = ROOT / "app/templates/_workout_quick_tools722.html"


def test_722_first_set_and_repeat_before_secondary_tools():
    html = MAIN.read_text(encoding="utf-8")
    tools = TOOLS.read_text(encoding="utf-8")
    for template in (html, tools):
        Environment().parse(template)
    assert html.count('{% include "_workout_quick_tools722.html" %}') == 2
    assert '{% if active and not equipment %}' in html
    markers = (
        'workout659-machine-picker',
        'workout662-nav',
        'id="workout659-log-form"',
        'workout659-repeat-button',
        'Rest Timer',
        '<summary>Load Setup</summary>',
        'Offline &amp; Draft Tools',
        'Planned Training Groups',
    )
    positions = [html.index(marker) for marker in markers]
    assert positions == sorted(positions)
    # Controls remain visible in active empty-catalog sessions via the
    # first include; normal active sessions render the same controls later.
    assert html.index('if active and not equipment') < html.index('if not equipment')
    assert html.rindex('{% include "_workout_quick_tools722.html" %}') > html.index('id="workout659-log-form"')
    assert tools.count('id="workout716-add-machine"') == 1
    assert 'href="/workouts#workout-sets657"' in tools
    for endpoint in ('/workouts/quick/machines', '/workouts/quick/machines/new'):
        assert f'action="{endpoint}"' in tools


def test_722_log_actions_retained_and_not_duplicated():
    html = MAIN.read_text(encoding="utf-8")
    assert html.count('action="/workouts/quick/sets"') == 1
    assert html.count('action="/workouts/quick/repeat"') == 1
    assert html.count('action="/workouts/quick/finish"') == 1
    assert html.count('formaction="/workouts/finish-review"') == 1
    assert html.count('id="workout659-save"') == 1
    assert html.count('name="weight_lb"') == 1
    assert html.count('name="reps"') == 1
    assert html.count('id="workout668-sync-status"') == 1
