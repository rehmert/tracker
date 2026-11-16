#!/usr/bin/env python3
"""Release 661: exact-SHA, read-only dashboard Workout integration source review."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE661 = "6a11a1a76a3d32d64bd8b98788dcc2eab4c0bece"
ALLOWED661 = frozenset({
    "app/workout_dashboard661.py",
    "app/routers/dashboard.py",
    "app/templates/dashboard.html",
    "app/templates/_workout_dashboard661.html",
    "app/static/css/tracker-workout-dashboard661.css",
    "tests/test_workout_dashboard661.py",
    "tests/browser/test_workout_dashboard661.py",
    "scripts/tracker-workout-dev661.sh",
    "scripts/tracker-workout-review661.py",
    "scripts/tracker-release-scoped661.sh",
    "docs/release-661-workout-dashboard.md",
})
REQUIRED661 = frozenset({
    "app/workout_dashboard661.py",
    "app/routers/dashboard.py",
    "app/templates/dashboard.html",
    "app/templates/_workout_dashboard661.html",
    "app/static/css/tracker-workout-dashboard661.css",
    "tests/test_workout_dashboard661.py",
    "tests/browser/test_workout_dashboard661.py",
    "scripts/tracker-workout-dev661.sh",
    "scripts/tracker-release-scoped661.sh",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("Source inspection failed: " + result.stderr[:190])
    return result.stdout


def check_one_change(
    root: Path, base: str, target: str, path: str, before: str, after: str,
) -> None:
    old = git(root, "show", f"{base}:{path}")
    new = git(root, "show", f"{target}:{path}")
    if old.count(before) != 1 or new != old.replace(before, after):
        raise ValueError("Unexpected shared file modification: " + path)


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE661 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Incorrect qualification baseline/target")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED661 <= changed or not changed <= ALLOWED661:
        raise ValueError("Unreviewed or missing source paths: " + repr(
            sorted((changed - ALLOWED661) | (REQUIRED661 - changed))
        ))
    old_route = git(root, "show", f"{base}:app/routers/dashboard.py")
    new_route = git(root, "show", f"{target}:app/routers/dashboard.py")
    for addition in (
        "from ..workout_dashboard661 import workout_dashboard661\n",
        "        workout_summary=workout_dashboard661(db, today_date),\n",
    ):
        if addition in old_route or new_route.count(addition) != 1:
            raise ValueError("Unexpected dashboard router modification")
        new_route = new_route.replace(addition, "", 1)
    if new_route != old_route:
        raise ValueError("Unreviewed change to dashboard logic")

    old_template = git(root, "show", f"{base}:app/templates/dashboard.html")
    new_template = git(root, "show", f"{target}:app/templates/dashboard.html")
    style = (
        '<script defer src="/static/js/tracker-dashboard-vial-pages598.js?v=598">'
        '</script>\n'
    )
    style_plus = (
        style + '<link rel="stylesheet" '
        'href="/static/css/tracker-workout-dashboard661.css?v=661">\n'
    )
    anchor = '  </nav>\n</section>\n<header class="dashboard-hero">'
    updated = (
        '  </nav>\n</section>\n'
        "{% include '_workout_dashboard661.html' %}\n"
        '<header class="dashboard-hero">'
    )
    if (old_template.count(style) != 1 or old_template.count(anchor) != 1
            or new_template != old_template.replace(style, style_plus).replace(
                anchor, updated
            )):
        raise ValueError("Unreviewed modification to existing dashboard panels")

    helper = (root / "app/workout_dashboard661.py").read_text(encoding="utf-8")
    for required in (
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSession654.completed_at.is_(None)",
        "WorkoutSet654.session_id == WorkoutSession654.id",
        "func.distinct(func.date(WorkoutSession654.started_at))",
        "RECENT_WORKOUT_LIMIT661 = 5",
        "RECENT_DAYS661 = 7",
        "LONG_DAYS661 = 28",
        "WorkoutSession654.started_at >= first",
        "WorkoutSession654.started_at < tomorrow",
        "WorkoutSession654.started_at.desc()",
        ".limit(RECENT_WORKOUT_LIMIT661)",
        "func.count(func.distinct(WorkoutSet654.equipment_id))",
    ):
        if required not in helper:
            raise ValueError("Missing frequency or isolation constraint: " + required)
    for forbidden in (
        "db.add(", "db.delete(", "db.commit(", "Base.metadata",
        "DROP TABLE", "ALTER TABLE", "@router.post(", "httpx", "requests.",
        "urlopen(", "exec(", "eval(",
    ):
        if forbidden in helper:
            raise ValueError("Unapproved dashboard write/network/schema change")
    panel = (root / "app/templates/_workout_dashboard661.html").read_text(
        encoding="utf-8"
    )
    for expected in (
        'data-dashboard-panel="9"',
        'data-dashboard-title="Workout activity"',
        "workout_summary.sessions7", "workout_summary.days7",
        "workout_summary.sessions28", "workout_summary.days28",
        "workout_summary.recent", "workout_summary.in_progress",
        'href="/workouts/quick"',
        'href="/workouts/analytics"',
        'href="/workouts/sessions/{{ row.session_id }}"',
        'href="/workouts"',
    ):
        if expected not in panel:
            raise ValueError("Missing customizable dashboard element: " + expected)
    if "<form" in panel or "fetch(" in panel:
        raise ValueError("Dashboard Workout panel must stay read only")
    print("WORKOUT_661_SCOPED_DASHBOARD_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
