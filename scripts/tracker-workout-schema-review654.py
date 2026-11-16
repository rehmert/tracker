#!/usr/bin/env python3
"""Release 654: fail-closed review of three additive Workout tables.

Invoked only from a pinned, isolated candidate worktree by tracker-release.sh.
No production data read/write and no schema migration performed here.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED654 = frozenset({
    ".github/workflows/workout654.yml",
    "app/workout_models654.py",
    "app/routers/workouts654.py",
    "app/templates/workouts654.html",
    "app/static/css/tracker-workouts654.css",
    "app/main.py",
    "app/templates/base.html",
    "scripts/tracker-release-scoped654.sh",
    "scripts/tracker-workout-schema-review654.py",
    "scripts/tracker-release.sh",
    "tests/test_workouts654.py",
    "docs/release-654-workout-foundation.md",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Git inspection failed: " + result.stderr[:200])
    return result.stdout


def review(root: Path, base: str, target: str) -> None:
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Candidate HEAD differs from pinned target")
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    required = {
        "app/workout_models654.py", "app/routers/workouts654.py",
        "app/main.py", "app/templates/base.html", "scripts/tracker-release.sh",
    }
    if not required <= changed or not changed <= ALLOWED654:
        raise ValueError(
            "Unreviewed/missing paths: "
            + repr(sorted((changed - ALLOWED654) | (required - changed)))
        )
    for old in ("app/models.py", "app/db.py", "app/migrations.py", "schema.sql"):
        if git(root, "show", f"{base}:{old}") != git(root, "show", f"{target}:{old}"):
            raise ValueError("Existing schema file changed: " + old)

    old_main = git(root, "show", f"{base}:app/main.py")
    new_main = git(root, "show", f"{target}:app/main.py")
    additions = (
        "from . import workout_models654  # noqa: F401 - register workout tables\n",
        "from .routers import workouts654\n",
        "app.include_router(workouts654.router)\n",
    )
    for line in additions:
        if line in old_main or new_main.count(line) != 1:
            raise ValueError("Unexpected Workout import/router registration")
        new_main = new_main.replace(line, "", 1)
    if new_main != old_main:
        raise ValueError("Other application startup changes found")

    old_nav = git(root, "show", f"{base}:app/templates/base.html")
    new_nav = git(root, "show", f"{target}:app/templates/base.html")
    expected_nav = "('/vitals','Vitals'),('/food','Food Journal')"
    if old_nav.count(expected_nav) != 1 or new_nav != old_nav.replace(
        expected_nav, "('/vitals','Vitals'),('/workouts','Workouts'),('/food','Food Journal')"
    ):
        raise ValueError("Unexpected global navigation change")

    source = (root / "app/workout_models654.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = {
        node.name: next((
            value.value for attr in node.body
            if isinstance(attr, ast.Assign)
            for target_node in attr.targets
            if isinstance(target_node, ast.Name) and target_node.id == "__tablename__"
            for value in [attr.value]
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        ), None)
        for node in tree.body if isinstance(node, ast.ClassDef)
    }
    expected = {
        "WorkoutEquipment654": "workout_equipment654",
        "WorkoutSession654": "workout_sessions654",
        "WorkoutSet654": "workout_sets654",
    }
    if found != expected:
        raise ValueError("Unexpected new table declarations")
    if "Base.metadata.drop_all" in source or "ALTER TABLE" in source:
        raise ValueError("Unexpected destructive or in-place schema operation")
    print("WORKOUT_654_APPEND_ONLY_SCHEMA_REVIEW=PASSED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root.resolve(), args.base, args.target)


if __name__ == "__main__":
    main()
