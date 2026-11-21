"""Release 723: prove Gym Mode CSS consolidation preserves exact rule order."""
from pathlib import Path
import subprocess

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BASE = "40088e446b66285aaa07caf40566e4de80864a98"
RELEASE_723 = "764efd20f0fe6ac643d7940eb8178387a530f842"
CSS = ROOT / "app/static/css"
TPL = ROOT / "app/templates/workout_quick659.html"


def historical(path, ref=BASE):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT),
         "show", f"{ref}:{path}"], text=True
    )


def test_723_merged_styles_are_byte_for_byte_ordered():
    old659 = historical("app/static/css/tracker-workouts659.css")
    old662 = historical("app/static/css/tracker-workouts662.css")
    old667 = historical("app/static/css/tracker-workout-gym667.css")
    old673 = historical("app/static/css/tracker-workout-ux673.css")
    merged659 = historical("app/static/css/tracker-workouts659.css", RELEASE_723)
    merged667 = historical("app/static/css/tracker-workout-gym667.css", RELEASE_723)
    assert merged659 == (old659 + "\n/* Release 723: consolidated former 662 machine finder, stepping and navigation rules. */\n" + old662)
    assert merged667 == (old667 + "\n/* Release 723: consolidated former 673 gym offline/draft UX rules. */\n" + old673)
    assert not (CSS / "tracker-workouts662.css").exists()
    assert not (CSS / "tracker-workout-ux673.css").exists()


def test_723_live_asset_reference_order_and_native_actions():
    html = historical("app/templates/workout_quick659.html", RELEASE_723)
    Environment().parse(html)
    assert html.count('tracker-workouts659.css?v=723') == 1
    assert html.count('tracker-workout-gym667.css?v=723') == 1
    assert 'tracker-workouts662.css' not in html
    assert 'tracker-workout-ux673.css' not in html
    assert html.index('tracker-workouts659.css?v=723') < html.index(
        'tracker-workout-targets666.css?v=666') < html.index(
        'tracker-workout-gym667.css?v=723') < html.index(
        'tracker-action-nav675.css?v=675')
    for action in ('/workouts/quick/sets', '/workouts/quick/repeat',
                   '/workouts/quick/finish'):
        assert f'action="{action}"' in html
    assert 'formaction="/workouts/finish-review"' in html
    assert html.count('id="workout659-log-form"') == 1
    assert 'id="workout659-machine-select"' in html
    assert 'id="workout668-sync-status"' in html
