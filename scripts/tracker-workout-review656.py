#!/usr/bin/env python3
"""Release 656 exact-SHA schema-free change review.

A source-only Workout update. Reject any data-model, schema, release-runner,
or unrelated changes; preserve the qualified Release 655 deployment process.
"""
from pathlib import Path
import argparse
import subprocess

BASE656 = "b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25"
ALLOWED656 = frozenset({
    "app/main.py",
    "app/routers/workouts656.py",
    "app/templates/workouts654.html",
    "app/templates/workout_progress656.html",
    "app/static/js/tracker-workouts656.js",
    "app/static/css/tracker-workouts656.css",
    "tests/test_workouts656.py",
    "scripts/tracker-release-scoped656.sh",
    "scripts/tracker-workout-dev656.sh",
    "scripts/tracker-workout-review656.py",
    "scripts/tracker-workout-camera-test656.cjs",
    "docs/release-656-workout-qr-progress.md",
})
REQUIRED656 = {
    "app/main.py", "app/routers/workouts656.py",
    "app/templates/workout_progress656.html",
    "app/static/js/tracker-workouts656.js",
    "tests/test_workouts656.py",
    "scripts/tracker-release-scoped656.sh",
    "scripts/tracker-workout-dev656.sh",
}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise ValueError("Git review failed: " + done.stderr.strip()[:200])
    return done.stdout


def validate(root: Path, base: str, target: str):
    if base != BASE656 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Unexpected base or candidate SHA")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED656 <= changed or not changed <= ALLOWED656:
        raise ValueError("Unreviewed change: " +
                         repr(sorted((changed - ALLOWED656) | (REQUIRED656 - changed))))
    # Shared application bootstrap must change only for a new read-only router.
    old = git(root, "show", f"{base}:app/main.py")
    new = git(root, "show", f"{target}:app/main.py")
    for inserted in (
        "from .routers import workouts656\n",
        "app.include_router(workouts656.router)\n",
    ):
        if inserted in old or new.count(inserted) != 1:
            raise ValueError("Invalid router registration")
        new = new.replace(inserted, "", 1)
    if new != old:
        raise ValueError("Unreviewed shared app startup change")
    source = (root / "app/routers/workouts656.py").read_text(encoding="utf-8")
    if not all(token in source for token in (
        'get_scoped_db390', '@router.get("/workouts/equipment/{equipment_id}/progress")',
        "MAX_RECENT_SETS656", "MAX_TREND_SESSIONS656",
    )):
        raise ValueError("Missing read-only workout route or scope")
    if any(token in source for token in (
        "db.add(", "db.commit(", "db.delete(", "@router.post(", "httpx", "requests.get",
    )):
        raise ValueError("Progress route not strictly read-only")
    js = (root / "app/static/js/tracker-workouts656.js").read_text(encoding="utf-8")
    if not all(token in js for token in (
        "BarcodeDetector", "getUserMedia", "encodeURIComponent(raw)",
        'window.location.assign("/workouts/qr?code="',
        "pagehide", "visibilitychange",
    )):
        raise ValueError("Incomplete internal-only camera scanner")
    if any(token in js for token in (
        "window.open(", "fetch(", "XMLHttpRequest", "eval(", "new Function(",
    )):
        raise ValueError("QR scanner must not fetch or open arbitrary destinations")
    print("WORKOUT_656_NO_SCHEMA_OR_UNREVIEWED_CHANGE=PASSED")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--target", required=True)
    args = p.parse_args()
    validate(args.root.resolve(), args.base, args.target)
