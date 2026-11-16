#!/usr/bin/env python3
"""Release 662: exact-SHA narrow UX-only review of the existing gym page."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE662 = "7456380bfe191cdc011a7dc692bd8c8cce59d1ed"
QUICK_BEFORE662 = "5143311b5481004501e9144f00314353453cfbe6"
QUICK_AFTER662 = "1558264badb86d842fae01c3c12418a6e9176f5e"

ALLOWED662 = frozenset({
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts662.css",
    "app/static/js/tracker-workouts662.js",
    "tests/test_workouts662.py",
    "tests/browser/test_workouts_quick662.py",
    "scripts/tracker-workout-dev662.sh",
    "scripts/tracker-workout-review662.py",
    "scripts/tracker-release-scoped662.sh",
    "docs/release-662-rapid-gym-ux.md",
})
REQUIRED662 = frozenset({
    "app/templates/workout_quick659.html",
    "app/static/css/tracker-workouts662.css",
    "app/static/js/tracker-workouts662.js",
    "tests/test_workouts662.py",
    "tests/browser/test_workouts_quick662.py",
    "scripts/tracker-workout-dev662.sh",
    "scripts/tracker-release-scoped662.sh",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Source verification failed: " + result.stderr[:180])
    return result.stdout.strip()


def validate(root: Path, base: str, target: str):
    if base != BASE662 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected DEV baseline or exact target")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED662 <= changed or not changed <= ALLOWED662:
        raise ValueError("Unexpected or missing changed files: " + repr(
            sorted((changed - ALLOWED662) | (REQUIRED662 - changed))
        ))

    # The only pre-existing source path is pinned to the exact reviewed Git
    # blob. No changes to logging functions, application routes, models,
    # session scoping, CSRF middleware or other Workout UI are allowed.
    before = git(root, "rev-parse", f"{base}:app/templates/workout_quick659.html")
    after = git(root, "rev-parse", f"{target}:app/templates/workout_quick659.html")
    if before != QUICK_BEFORE662 or after != QUICK_AFTER662:
        raise ValueError("Rapid Gym page differs from reviewed additive UX")

    html = (root / "app/templates/workout_quick659.html").read_text(
        encoding="utf-8"
    )
    for required in (
        'tracker-workouts659.js?v=659',
        'tracker-workouts662.js?v=662',
        'tracker-workouts662.css?v=662',
        'id="workout662-directory"',
        'id="workout662-search"',
        'id="workout662-results"',
        'data-search662="{{ item.name }} {{ item.gym }}"',
        'aria-current="page"',
        'data-step659="weight" data-delta659="-2.5"',
        'data-step659="weight" data-delta659="2.5"',
        'data-step659="reps" data-delta659="-5"',
        'data-step659="reps" data-delta659="5"',
        'type="reset" class="workout662-restore"',
        'class="workout662-nav"',
        'Next Machine: {{ next_machine.name }}',
        'action="/workouts/quick/sets"',
        'action="/workouts/quick/repeat"',
        'action="/workouts/quick/finish"',
        'id="workout659-rest-display"',
    ):
        if required not in html:
            raise ValueError("Missing safe quick-logging control: " + required)

    script = (root / "app/static/js/tracker-workouts662.js").read_text(
        encoding="utf-8"
    )
    for required in (
        'root.querySelector("form.workout659-machine-picker")',
        'select[name="machine"]',
        'selector.addEventListener("change"',
        'picker.requestSubmit()',
        'link.dataset.search662',
        'link.hidden = !match',
        'search.addEventListener("input", refresh)',
    ):
        if required not in script:
            raise ValueError("Missing progressive-enhancement behavior: " + required)
    for forbidden in (
        "fetch(", "XMLHttpRequest", "localStorage", "sessionStorage",
        "document.cookie", "innerHTML", "eval(", "new Function", "http://",
        "https://", ".post(", "method = 'POST'", 'method = "POST"',
    ):
        if forbidden in script:
            raise ValueError("New UX script must not write or contact remote APIs")

    css = (root / "app/static/css/tracker-workouts662.css").read_text(
        encoding="utf-8"
    )
    if "a[hidden]" not in css or "max-height:300px" not in css:
        raise ValueError("Machine directory accessibility and bounds missing")
    print("WORKOUT_662_REVIEWED_UX_ONLY_SOURCE=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
