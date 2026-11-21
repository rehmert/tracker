"""Release 724: Gym Mode has one set-adjacent machine navigation."""
from pathlib import Path
import subprocess
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BASE = "764efd20f0fe6ac643d7940eb8178387a530f842"
MAIN = ROOT / "app/templates/workout_quick659.html"
CSS = ROOT / "app/static/css"


def historical(path):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT),
         "show", f"{BASE}:{path}"], text=True
    )


def test_724_no_duplicate_routine_machine_navigation_or_modified_write_paths():
    html = MAIN.read_text(encoding="utf-8")
    Environment().parse(html)
    assert html.count('class="workout662-nav"') == 1
    assert "workout659-move" not in html
    assert html.count('/workouts/quick?machine={{ previous_machine.id }}') == 1
    assert html.count('/workouts/quick?machine={{ next_machine.id }}') == 1
    assert html.index('id="workout659-save"') < html.index(
        'class="workout662-nav"') < html.index(
        '<summary>Load Setup</summary>') < html.index('Rest Timer')
    for path in ('/workouts/quick/sets', '/workouts/quick/repeat',
                 '/workouts/quick/finish'):
        assert html.count(f'action="{path}"') == 1
    assert html.count('{% include "_workout_quick_tools722.html" %}') == 2
    assert 'tracker-workouts659.css?v=724' in html
    assert 'tracker-workout-gym667.css?v=724' in html


def test_724_only_orphaned_styles_removed_from_prior_css():
    old659 = historical("app/static/css/tracker-workouts659.css")
    new659 = (CSS / "tracker-workouts659.css").read_text()
    old667 = historical("app/static/css/tracker-workout-gym667.css")
    new667 = (CSS / "tracker-workout-gym667.css").read_text()
    unused = (
        ".workout659-move {",
        ".workout659-move-button {",
        ".workout659-move-next {",
    )
    for selector in unused:
        assert selector not in new659
    for line in old659.splitlines(keepends=True):
        if line.startswith(unused):
            continue
        assert line in new659
    assert ".workout662-nav" in new659
    assert ".ux673-gym-links" not in new667
    assert ".ux673-gym-offline" in new667
    assert ".ux673-gym-offline-content button" in new667
    assert new667.startswith(old667.split('.ux673-gym-links {', 1)[0])
    assert new659.count("{") == new659.count("}")
    assert new667.count("{") == new667.count("}")
