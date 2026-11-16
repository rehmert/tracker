#!/usr/bin/env python3
"""Release 659: pinned, schema-free and bounded Gym Floor Mode source review."""
from pathlib import Path
import argparse
import subprocess

BASE659 = "8ff6dea1ac470e73fa886984238d958954de6d27"
ALLOWED659 = frozenset({
    "app/main.py",
    "app/routers/workouts659.py",
    "app/templates/workouts654.html",
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts659.css",
    "app/static/js/tracker-workouts659.js",
    "tests/test_workouts659.py",
    "tests/browser/test_workouts_quick659.py",
    "scripts/tracker-workout-dev659.sh",
    "scripts/tracker-workout-review659.py",
    "scripts/tracker-release-scoped659.sh",
    "docs/release-659-rapid-gym-floor.md",
})
REQUIRED659 = frozenset({
    "app/main.py",
    "app/routers/workouts659.py",
    "app/templates/workouts654.html",
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts659.css",
    "app/static/js/tracker-workouts659.js",
    "tests/test_workouts659.py",
    "tests/browser/test_workouts_quick659.py",
    "scripts/tracker-workout-dev659.sh",
    "scripts/tracker-release-scoped659.sh",
})


def git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if process.returncode:
        raise ValueError("Source verification failed: " + process.stderr[:180])
    return process.stdout


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE659 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Unexpected qualified base or candidate SHA")
    git(root, "merge-base", "--is-ancestor", base, target)
    files = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED659 <= files or not files <= ALLOWED659:
        raise ValueError("Unreviewed change set: " +
                         repr(sorted((files - ALLOWED659) | (REQUIRED659 - files))))

    old_main = git(root, "show", f"{base}:app/main.py")
    new_main = git(root, "show", f"{target}:app/main.py")
    for line in (
        "from .routers import workouts659\n",
        "app.include_router(workouts659.router)\n",
    ):
        if line in old_main or new_main.count(line) != 1:
            raise ValueError("Unexpected shared application router registration")
        new_main = new_main.replace(line, "", 1)
    if new_main != old_main:
        raise ValueError("Other shared startup changes not approved")

    old_home = git(root, "show", f"{base}:app/templates/workouts654.html")
    new_home = git(root, "show", f"{target}:app/templates/workouts654.html")
    old_line = (
        '  <p><a href="/workouts/backfill" class="workout658-history-link">'
        "Log a Previous Workout</a></p>"
    )
    new_line = (
        '  <p><a href="/workouts/quick" class="workout659-entry-link">'
        'Open Rapid Gym Mode</a> · <a href="/workouts/backfill" '
        'class="workout658-history-link">Log a Previous Workout</a></p>'
    )
    if old_home.count(old_line) != 1 or new_home != old_home.replace(old_line, new_line):
        raise ValueError("Unexpected modification of main Workout workflow")

    route = (root / "app/routers/workouts659.py").read_text(encoding="utf-8")
    for token in (
        "get_scoped_db390",
        '@router.get("/workouts/quick")',
        '@router.post("/workouts/quick/start")',
        '@router.post("/workouts/quick/sets")',
        '@router.post("/workouts/quick/repeat")',
        '@router.post("/workouts/quick/finish")',
        'add_set654(', 'repeat_last_set655(', 'start_routine655(',
        'start654(', 'finish654(', 'active654(db)',
        'session_id == active.id',
        "WorkoutSessionRoutine655",
    ):
        if token not in route:
            raise ValueError("Missing guarded quick-mode operation: " + token)
    for forbidden in (
        "db.commit(", "db.add(", "Base.metadata", "ALTER TABLE", "DROP TABLE",
        "httpx", "requests.", "urlopen(", "get_engine(", "exec(", "eval(",
    ):
        if forbidden in route:
            raise ValueError("Unreviewed quick-mode side effect: " + forbidden)
    page = (root / "app/templates/workout_quick659.html").read_text(encoding="utf-8")
    for needle in (
        'action="/workouts/quick/sets"', 'action="/workouts/quick/repeat"',
        'action="/workouts/quick/finish"', 'id="workout659-rest-display"',
        'id="workout659-machine-select"', 'name="source_set_id"',
        "data-session-id=", "data-last-set-id=", "data-logged=",
        "Next: {{ next_machine.name }}",
    ):
        if needle not in page:
            raise ValueError("Missing mobile-first control: " + needle)
    javascript = (root / "app/static/js/tracker-workouts659.js").read_text(
        encoding="utf-8"
    )
    for required in (
        "window.sessionStorage", "sessionId", "lastId",
        "seen-set", "deadline", "window.setInterval",
    ):
        if required not in javascript:
            raise ValueError("Rest timer continuity missing: " + required)
    print("WORKOUT_659_EXACT_SOURCE_ONLY_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
