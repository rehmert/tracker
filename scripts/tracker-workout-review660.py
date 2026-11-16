#!/usr/bin/env python3
"""Release 660 exact-SHA review for completed-only, read-only workout analytics."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE660 = "a02b70bb085533ff4ec23bae5e2bde9b25e40360"
ALLOWED660 = frozenset({
    "app/main.py",
    "app/routers/workouts660.py",
    "app/templates/workout_analytics660.html",
    "app/templates/workouts654.html",
    "app/templates/workout_progress656.html",
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts660.css",
    "tests/test_workouts660.py",
    "scripts/tracker-workout-dev660.sh",
    "scripts/tracker-workout-review660.py",
    "scripts/tracker-release-scoped660.sh",
    "docs/release-660-strength-progress.md",
})
REQUIRED660 = frozenset({
    "app/main.py",
    "app/routers/workouts660.py",
    "app/templates/workout_analytics660.html",
    "app/templates/workouts654.html",
    "app/templates/workout_progress656.html",
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts660.css",
    "tests/test_workouts660.py",
    "scripts/tracker-workout-dev660.sh",
    "scripts/tracker-release-scoped660.sh",
})


def git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if process.returncode:
        raise ValueError("Git source inspection failed: " + process.stderr[:200])
    return process.stdout


def check_one_insertion(
    root: Path, base: str, target: str, path: str, before: str, after: str,
) -> None:
    prior = git(root, "show", f"{base}:{path}")
    current = git(root, "show", f"{target}:{path}")
    if prior.count(before) != 1 or current != prior.replace(before, after):
        raise ValueError("Unexpected modification to shared UI: " + path)


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE660 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Unexpected baseline or candidate SHA")
    git(root, "merge-base", "--is-ancestor", base, target)
    paths = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED660 <= paths or not paths <= ALLOWED660:
        raise ValueError("Unreviewed/missing paths: " +
                         repr(sorted((paths - ALLOWED660) | (REQUIRED660 - paths))))

    prior = git(root, "show", f"{base}:app/main.py")
    current = git(root, "show", f"{target}:app/main.py")
    for addition in (
        "from .routers import workouts660\n",
        "app.include_router(workouts660.router)\n",
    ):
        if addition in prior or current.count(addition) != 1:
            raise ValueError("Unexpected application router registration")
        current = current.replace(addition, "", 1)
    if current != prior:
        raise ValueError("Other startup modifications not approved")

    old_home = (
        '  <p><a href="/workouts/quick" class="workout659-entry-link">'
        'Open Rapid Gym Mode</a> · <a href="/workouts/backfill" '
        'class="workout658-history-link">Log a Previous Workout</a></p>'
    )
    new_home = (
        '  <p><a href="/workouts/quick" class="workout659-entry-link">'
        'Open Rapid Gym Mode</a> · <a href="/workouts/analytics">'
        'Strength Progress</a> · <a href="/workouts/backfill" '
        'class="workout658-history-link">Log a Previous Workout</a></p>'
    )
    check_one_insertion(
        root, base, target, "app/templates/workouts654.html",
        old_home, new_home,
    )
    old_history_title = '  <h1>{{ machine.name }} — Progress</h1>'
    check_one_insertion(
        root, base, target, "app/templates/workout_progress656.html",
        old_history_title,
        old_history_title + '\n'
        '  <p><a href="/workouts/analytics?machine={{ machine.id }}">'
        'View Strength Analytics &amp; Exact-Rep Trends</a></p>',
    )
    old_quick = '      <p><a href="/workouts">← Full Workout Tracker</a></p>'
    check_one_insertion(
        root, base, target, "app/templates/workout_quick659.html",
        old_quick,
        '      <p><a href="/workouts">← Full Workout Tracker</a> · '
        '<a href="/workouts/analytics">Strength Progress</a></p>',
    )

    route = (root / "app/routers/workouts660.py").read_text(encoding="utf-8")
    for required in (
        "get_scoped_db390",
        '@router.get("/workouts/analytics")',
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSet654.equipment_id == selected.id",
        "WorkoutSet654.reps == reps_selected",
        "MAX_SESSION_POINTS660 = 20",
        "MAX_REP_CHOICES660 = 12",
        "func.count(func.distinct(WorkoutSession654.id))",
        "func.sum(entry_volume)",
        "func.max(WorkoutSet654.weight_lb)",
        ".order_by(",
        "chart_points660(session_volumes)",
        "chart_points660(exact_weights)",
    ):
        if required not in route:
            raise ValueError("Missing completed-session analytic protection: " + required)
    for forbidden in (
        "db.add(", "db.delete(", "db.commit(", "@router.post(",
        "Base.metadata", "ALTER TABLE", "DROP TABLE",
        "httpx", "requests.", "urlopen(", "get_engine(",
    ):
        if forbidden in route:
            raise ValueError("Unapproved analytics write or schema change: " + forbidden)

    ui = (root / "app/templates/workout_analytics660.html").read_text(
        encoding="utf-8"
    )
    for required in (
        'action="/workouts/analytics"',
        'name="machine"',
        'name="reps"',
        "Recorded Personal Records",
        "Volume by Workout",
        "Compare the Same Repetition Count",
        "completed workouts only",
        "Recorded volume (lb × reps)",
        'href="/workouts/sessions/{{ row.session_id }}"',
    ):
        if required not in ui:
            raise ValueError("Missing accessible analytics output: " + required)
    print("WORKOUT_660_EXACT_SOURCE_ONLY_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
