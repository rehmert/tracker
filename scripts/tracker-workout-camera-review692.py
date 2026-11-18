#!/usr/bin/env python3
"""Release 692: exact-scope retirement of Workout QR camera, no migration."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess

BASE = "869ada02eb9ac523ca9e8ce7c19ed6b92b303d68"
EXPECTED = frozenset({
    "app/templates/workouts654.html",
    "app/routers/workouts656.py",
    "app/static/css/tracker-workouts656.css",
    "app/static/js/tracker-workouts656.js",
    "scripts/tracker-workout-camera-test656.cjs",
    "tests/test_workouts656.py",
    "tests/test_workout_no_camera692.py",
    "scripts/tracker-workout-camera-review692.py",
    "scripts/tracker-release-scoped692.sh",
    "scripts/tracker-preview692.sh",
})


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True,
    )


def review(root: Path, base: str, target: str) -> None:
    if base != BASE:
        raise ValueError("Wrong qualified Release 691 baseline")
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Must review an immutable candidate checkout")
    subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root),
         "merge-base", "--is-ancestor", base, target],
        check=True,
    )
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != EXPECTED:
        raise ValueError(f"Unexpected Release 692 changes: {sorted(changed ^ EXPECTED)}")
    deleted = set(git(root, "diff", "--name-only", "--diff-filter=D",
                      base, target).splitlines())
    if deleted != {
        "app/static/js/tracker-workouts656.js",
        "scripts/tracker-workout-camera-test656.cjs",
    }:
        raise ValueError("Old camera implementation or DOM harness not retired")
    if git(root, "diff", "--name-only", base, target, "--",
           "app/models.py", "app/migrations.py",
           "app/workout_models654.py", "app/workout_models655.py",
           "app/workout_models667.py", "app/workout_models668.py",
           "app/scoped_db390.py"):
        raise ValueError("Scanner removal must not change database or auth models")

    old_html = git(root, "show", f"{base}:app/templates/workouts654.html")
    html = (root / "app/templates/workouts654.html").read_text()
    assert 'name="code"' in html and 'action="/workouts/qr"' in html
    assert 'name="qr_value"' in html and "Equipment &amp; Logging" in html
    assert '"/workouts/sets"' in html and "Progress &amp; History" in html
    for removed in (
        "Scan QR with Camera", "Stop Camera", "workout-qr-camera656",
        "tracker-workouts656.js", "data-start656", "data-preview656",
        "data-status656", "unmapped_qr", "<video",
    ):
        if removed in html:
            raise ValueError("Camera scan UI or orphaned state still present: " + removed)
    assert "Scan QR with Camera" in old_html and "tracker-workouts656.js" in old_html

    old_route = git(root, "show", f"{base}:app/routers/workouts656.py")
    route = (root / "app/routers/workouts656.py").read_text()
    ast.parse(route, filename="app/routers/workouts656.py")
    assert '@router.get("/workouts/qr/scan")' in old_route
    assert '@router.get("/workouts/qr/scan")' not in route
    assert 'get_scoped_db390' in route
    assert '@router.get("/workouts/equipment/{equipment_id}/progress")' in route
    assert "def trend_points656(" in route
    assert "db.commit(" not in route and "db.delete(" not in route

    css = (root / "app/static/css/tracker-workouts656.css").read_text()
    assert ".workout656-camera" not in css
    assert ".workout656-preview" not in css
    assert ".workout656-progress" in css

    assert not (root / "app/static/js/tracker-workouts656.js").exists()
    assert not (root / "scripts/tracker-workout-camera-test656.cjs").exists()
    print("RELEASE_692_CAMERA_REMOVAL_SOURCE_REVIEW=PASSED")
    print("RELEASE_692_SCHEMA_CHANGE=NONE")
    print("RELEASE_692_MANUAL_QR_AND_WORKOUT_LOGGING=PRESERVED")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--target", required=True)
    a = p.parse_args()
    review(a.root.resolve(), a.base, a.target)


if __name__ == "__main__":
    main()
