#!/usr/bin/env python3
"""Release 666: fail-closed exact-source review for read-only in-gym targets."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE666 = "fe34a4060cd8b5933322d91d3e011206c87e21ef"

# Exactly two already-qualified files may change, to the reviewed blobs.
REVIEWED666 = {
    "app/routers/workouts659.py": (
        "b245bd7a938e0efc827c63ce1cbc05b0b09a82e0",
        "bcbe4f5c43e0b242744822bb7e931b0c02937b58",
    ),
    "app/templates/workout_quick659.html": (
        "b5e88539383de165510581233988c4a867102b2a",
        "a8bce2a205be83fc6bfe8e72e1f9477fd3ff9f6b",
    ),
}
NEW666 = frozenset({
    "app/static/js/tracker-workout-targets666.js",
    "app/static/css/tracker-workout-targets666.css",
    "tests/test_workouts666.py",
    "tests/browser/test_workout_targets666.py",
    "scripts/tracker-workout-dev666.sh",
    "scripts/tracker-workout-review666.py",
    "scripts/tracker-release-scoped666.sh",
    "docs/release-666-workout-target-integration.md",
})
REQUIRED666 = frozenset(REVIEWED666) | NEW666


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Workout source inspection failed: " + proc.stderr[:180])
    return proc.stdout.strip()


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE666 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected DEV Release 665 baseline or Release 666 target")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != REQUIRED666:
        raise ValueError("Unexpected Release 666 file scope: " +
                         repr(sorted(changed ^ REQUIRED666)))
    for path, (before, after) in REVIEWED666.items():
        old = git(root, "rev-parse", f"{base}:{path}")
        new = git(root, "rev-parse", f"{target}:{path}")
        if (old, new) != (before, after):
            raise ValueError("Unexpected change to existing Workout route or UI: " + path)

    router = (root / "app/routers/workouts659.py").read_text(
        encoding="utf-8"
    )
    for expected in (
        "get_scoped_db390",
        "WorkoutRoutineItem655.routine_id == routine.id",
        "if chosen and item.equipment_id == chosen.id",
        "plan_item_id=plan_item_id",
        '@router.post("/workouts/quick/sets")',
        "response = add_set654(",
        "response = finish654(db=db)",
    ):
        if expected not in router:
            raise ValueError("Routine item or original set route changed: " + expected)
    if router.count("@router.post(") != 5:
        raise ValueError("Unexpected change to Rapid Gym POST endpoints")

    template = (root / "app/templates/workout_quick659.html").read_text(
        encoding="utf-8"
    )
    for expected in (
        "{% if routine and plan_item_id %}",
        'data-routine-id666="{{ routine.id }}"',
        'data-item-id666="{{ plan_item_id }}"',
        'id="workout666-target-values"',
        'id="workout666-targets-status"',
        'data-target666="sets"',
        'data-target666="reps"',
        'data-target666="weight"',
        'href="/workouts/routines/{{ routine.id }}/plan"',
        "Browser-only intentions, not logged sets",
        'src="/static/js/tracker-workout-targets666.js?v=666"',
        'href="/static/css/tracker-workout-targets666.css?v=666"',
        'action="/workouts/quick/sets"',
        'action="/workouts/quick/repeat"',
        'action="/workouts/quick/finish"',
        'formaction="/workouts/finish-review"',
    ):
        if expected not in template:
            raise ValueError("Workout target or existing log action missing: " + expected)
    panel = template.split('id="workout666-targets"', 1)[1].split(
        "{% endif %}", 1
    )[0]
    if "<form" in panel or "<input" in panel:
        raise ValueError("Targets must never become editable logging form fields")

    js = (root / "app/static/js/tracker-workout-targets666.js").read_text(
        encoding="utf-8"
    )
    for expected in (
        "tracker.workout665.plan.routine.",
        "localStorage.getItem", "JSON.parse",
        "payload.version !== 1", "Number.isFinite", "Number.isInteger",
        "data-target666", "textContent",
        "list.hidden = true", "list.hidden = false",
        'window.addEventListener("storage"',
        'window.addEventListener("pageshow"',
    ):
        if expected not in js:
            raise ValueError("Read-only local target guard missing: " + expected)
    for forbidden in (
        "localStorage.setItem", "localStorage.removeItem",
        "fetch(", "XMLHttpRequest", "sendBeacon(", "WebSocket",
        "FormData(", "document.cookie", "innerHTML", "outerHTML",
        "requestSubmit(", ".submit(", "http://", "https://",
        "getElementById(\"workout659-weight",
        "getElementById(\"workout659-reps",
    ):
        if forbidden in js:
            raise ValueError("Read-only workout target code may not write: " + forbidden)

    css = (root / "app/static/css/tracker-workout-targets666.css").read_text(
        encoding="utf-8"
    )
    if ".workout666-target-values[hidden]{display:none;}" not in css:
        raise ValueError("Missing hidden-target CSS safeguard")
    print("WORKOUT_666_EXACT_READ_ONLY_TARGET_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
