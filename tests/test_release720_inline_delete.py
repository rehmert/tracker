"""Release 720: compact, adjacent Edit and Delete controls for workouts."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def test_720_delete_action_renders_inline_with_confirmation_and_signed_post():
    workout = SimpleNamespace(
        id=721, started_at=datetime(2026, 11, 20, 10, 15), completed_at=None
    )
    fragment = templates.env.get_template("_workout_delete719.html").render(
        delete_workout=workout
    )
    assert '<form class="workout720-delete-form"' in fragment
    assert 'id="workout719-delete-721"' in fragment
    assert 'method="post" action="/workouts/sessions/721/delete"' in fragment
    assert 'onsubmit="return confirm(' in fragment
    assert 'name="confirm_delete" value="yes"' in fragment
    assert 'name="reason"' in fragment
    assert 'Started by mistake' in fragment
    assert 'name="expected_started_at"' in fragment
    assert '2026-11-20T10:15:00' in fragment
    assert 'aria-label="Delete workout started' in fragment
    assert '>Delete</button>' in fragment
    assert '<details' not in fragment
    assert '<input type="checkbox"' not in fragment

    workout.completed_at = datetime(2026, 11, 20, 11)
    completed = templates.env.get_template("_workout_delete719.html").render(
        delete_workout=workout
    )
    assert 'Deleted workout from history' in completed


def test_720_edit_and_delete_share_same_recent_row_and_review_nav():
    rows = (ROOT / "app/templates/workouts654.html").read_text()
    opening = rows.index('<span class="workout720-row-actions">')
    closing = rows.index('</span>', opening)
    row_actions = rows[opening:closing]
    assert "Edit Workout</a>" in row_actions
    assert '{% include "_workout_delete719.html" %}' in row_actions
    assert row_actions.index("Edit Workout</a>") < row_actions.index(
        '{% include "_workout_delete719.html" %}'
    )
    history = (ROOT / "app/templates/workout_history654.html").read_text()
    review = (ROOT / "app/templates/workout_review663.html").read_text()
    for template in (history, review):
        nav = template.split("</nav>", 1)[0]
        assert '{% include "_workout_delete719.html" %}' in nav
    quick = (ROOT / "app/templates/workout_quick659.html").read_text()
    assert "Delete Accidental Workout</a>" in quick
    assert '{% include "_workout_delete719.html" %}' not in quick
    css = (ROOT / "app/static/css/tracker-workout-session719.css").read_text()
    assert "min-height:44px" in css
    assert ".workout720-row-actions" in css
    for template in (rows, history, review):
        assert "tracker-workout-session719.css?v=720" in template
