#!/usr/bin/env python3
"""Release 658 exact-SHA source-only past Workout entry review."""
from pathlib import Path
import argparse
import subprocess

BASE658 = "b9487d4b1fab176255b398833c51c9a2da79f042"
ALLOWED658 = frozenset({
    "app/main.py",
    "app/routers/workouts658.py",
    "app/templates/workouts654.html",
    "app/templates/workout_backfill658.html",
    "app/static/js/tracker-workouts658.js",
    "app/static/css/tracker-workouts658.css",
    "tests/test_workouts658.py",
    "scripts/tracker-workout-dev658.sh",
    "scripts/tracker-workout-review658.py",
    "scripts/tracker-release-scoped658.sh",
    "docs/release-658-retroactive-workout.md",
})
REQUIRED658 = frozenset({
    "app/main.py", "app/routers/workouts658.py",
    "app/templates/workouts654.html", "app/templates/workout_backfill658.html",
    "tests/test_workouts658.py", "scripts/tracker-workout-dev658.sh",
    "scripts/tracker-release-scoped658.sh",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Source inspection failed: " + result.stderr[:200])
    return result.stdout


def validate(root: Path, base: str, target: str):
    if base != BASE658 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Candidate SHA or review base differs")
    git(root, "merge-base", "--is-ancestor", base, target)
    names = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED658 <= names or not names <= ALLOWED658:
        raise ValueError("Unreviewed / absent paths: " +
                         repr(sorted((names - ALLOWED658) | (REQUIRED658 - names))))

    old_main = git(root, "show", f"{base}:app/main.py")
    new_main = git(root, "show", f"{target}:app/main.py")
    for inserted in (
        "from .routers import workouts658\n",
        "app.include_router(workouts658.router)\n",
    ):
        if inserted in old_main or new_main.count(inserted) != 1:
            raise ValueError("Unexpected application bootstrap change")
        new_main = new_main.replace(inserted, "", 1)
    if new_main != old_main:
        raise ValueError("Unreviewed shared startup change")

    home_before = git(root, "show", f"{base}:app/templates/workouts654.html")
    home_after = git(root, "show", f"{target}:app/templates/workouts654.html")
    anchor = (
        "  <h1>Workouts</h1>\n"
        "  <p class=\"note\">Nautilus machines and free weights. "
        "Log only the load and repetitions you actually completed.</p>"
    )
    extra = (
        "\n  <p><a href=\"/workouts/backfill\" "
        "class=\"workout658-history-link\">Log a Previous Workout</a></p>"
    )
    if home_before.count(anchor) != 1 or home_after != home_before.replace(
        anchor, anchor + extra
    ):
        raise ValueError("Unreviewed change to established Workout page")

    source = (root / "app/routers/workouts658.py").read_text(encoding="utf-8")
    for required in (
        "get_scoped_db390",
        '@router.get("/workouts/backfill")',
        '@router.post("/workouts/backfill")',
        "MAX_HISTORICAL_SETS658 = 40",
        "MAX_HISTORICAL_HOURS658 = 12",
        "math.isfinite(pounds)",
        "end > now",
        "db.add(session)", "db.flush()", "db.commit()",
        "WorkoutSessionRoutine655", "session_id=session.id",
        "WorkoutSet654(session_id=session.id, **entry)",
    ):
        if required not in source:
            raise ValueError("Missing validated historical entry protection: " + required)
    for forbidden in (
        "Base.metadata", "ALTER TABLE", "DROP TABLE", "drop_all(",
        "httpx", "requests.", "urlopen(", "eval(", "exec(",
    ):
        if forbidden in source:
            raise ValueError("Unapproved schema / network / dynamic execution")

    ui = (root / "app/templates/workout_backfill658.html").read_text(encoding="utf-8")
    for expected in (
        'action="/workouts/backfill"', 'name="start_time"',
        'name="end_time"', 'name="equipment_id"',
        'name="set_time"', 'name="routine_id"',
        "Save Completed Workout",
    ):
        if expected not in ui:
            raise ValueError("Historical entry field missing: " + expected)
    print("WORKOUT_658_SCHEMA_FREE_SCOPED_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
