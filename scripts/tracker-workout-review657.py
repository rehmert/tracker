#!/usr/bin/env python3
"""Release 657: exact-commit, no-schema Workout mobile workflow review.

Allow only the active-workout correction endpoints and corresponding scoped
read-only UI changes. Historical models and the release runner remain intact.
"""
from pathlib import Path
import argparse
import subprocess

BASE657 = "06b8be62f5be455df47be87bc5157b41fcac8783"
ALLOWED657 = frozenset({
    "app/main.py",
    "app/routers/workouts654.py",
    "app/routers/workouts657.py",
    "app/templates/workouts654.html",
    "app/static/css/tracker-workouts657.css",
    "tests/test_workouts657.py",
    "scripts/tracker-workout-review657.py",
    "scripts/tracker-workout-dev657.sh",
    "scripts/tracker-release-scoped657.sh",
    "docs/release-657-workout-mobile.md",
})
REQUIRED657 = {
    "app/main.py",
    "app/routers/workouts657.py",
    "app/templates/workouts654.html",
    "tests/test_workouts657.py",
    "scripts/tracker-release-scoped657.sh",
    "scripts/tracker-workout-dev657.sh",
}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        check=False, text=True, capture_output=True,
    )
    if result.returncode:
        raise ValueError("Source inspection failed: " + result.stderr.strip()[:160])
    return result.stdout


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE657 or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Unexpected base or candidate commit")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not REQUIRED657 <= changed or not changed <= ALLOWED657:
        raise ValueError("Unreviewed Release 657 change: " +
                         repr(sorted((changed - ALLOWED657) | (REQUIRED657 - changed))))
    before = git(root, "show", f"{base}:app/main.py")
    after = git(root, "show", f"{target}:app/main.py")
    for inserted in (
        "from .routers import workouts657\n",
        "app.include_router(workouts657.router)\n",
    ):
        if inserted in before or after.count(inserted) != 1:
            raise ValueError("Unexpected router registration")
        after = after.replace(inserted, "", 1)
    if after != before:
        raise ValueError("Unreviewed shared application bootstrap modification")

    old = git(root, "show", f"{base}:app/routers/workouts654.py")
    new = git(root, "show", f"{target}:app/routers/workouts654.py")
    marker = '@router.post("/workouts/equipment")'
    if old.count(marker) != 1 or new.count(marker) != 1:
        raise ValueError("Workout 654 anchor missing")
    if old.split(marker, 1)[1] != new.split(marker, 1)[1]:
        raise ValueError("Release 654 set logging and history endpoints must not change")
    for needle in ("logged_ids =", "next_machine =", "counts_this_session =",
                   "routine_logged_count=", "routine_total="):
        if needle not in new.split(marker, 1)[0]:
            raise ValueError("Missing bounded in-session navigation data: " + needle)

    mutation = (root / "app/routers/workouts657.py").read_text(encoding="utf-8")
    for check in (
        "get_scoped_db390", "active654(db)", "entry.session_id != current.id",
        '@router.post("/workouts/sets/{set_id}/edit")',
        '@router.post("/workouts/sets/{set_id}/delete")',
        'if confirm_delete != "yes":',
        "math.isfinite(weight_lb)", "1 <= reps <= 200",
        "db.commit()",
    ):
        if check not in mutation:
            raise ValueError("Missing scoped/validated set correction guard: " + check)
    for forbidden in (
        "get_engine(", "Base.metadata", "ALTER TABLE", "DROP TABLE",
        "eval(", "exec(", "httpx", "requests.", "urlopen(", "@router.get(",
    ):
        if forbidden in mutation:
            raise ValueError("Unexpected operation in active-set correction route")

    template = (root / "app/templates/workouts654.html").read_text(encoding="utf-8")
    for expected in (
        "workout657-set-actions", "workout657-delete-form",
        'name="confirm_delete" value="yes" required',
        "workout657-next-link", "workout657-progress",
    ):
        if expected not in template:
            raise ValueError("Missing confirmed edit / next exercise UI: " + expected)

    print("WORKOUT_657_SOURCE_ONLY_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
