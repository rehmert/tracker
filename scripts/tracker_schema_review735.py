#!/usr/bin/env python3
"""One-time signed 727 -> 735 PROD additive tablet-schema catch-up review.

No live writes. This review is an additional condition, never a replacement
for signed DEV approval, verified production backups or schema migration gates.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROD_727 = "3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2"
MILESTONES = (
    ("729", "d2597c5bfab3c76e1701a42af00ab5ce41553818"),
    ("730", "13ed014d24ba5658a69ccb15b6d8e1a247c7575c"),
    ("731", "0bc005f9c1e5b1353a67755aeeb2940140a7c74f"),
    ("732", "1906a69408e7dd00cb9044f77cd208566aed25df"),
    ("733", "28003549a8d0d69ac7ea23d8addd699a71a5a226"),
    ("734", "2421fde33dfae626022529f046c9b21035ad6d62"),
)
SCHEMA_INTRO = MILESTONES[2][1]
DEV_730 = MILESTONES[1][1]
SHA = re.compile(r"[0-9a-f]{40}\Z")
SCHEMA_PATHS = frozenset({
    "app/models.py",
    "app/db.py", "app/migrations.py", "app/schema.py",
    "app/workout_models654.py", "app/workout_models655.py",
    "app/workout_models667.py", "app/workout_models668.py",
    "alembic.ini",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "safe.directory=" + str(root), "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Git review operation failed: " + args[0])
    return result.stdout.strip()


def review(root: Path, base: str, target: str) -> None:
    root = root.resolve()
    if base != PROD_727 or not SHA.fullmatch(target) or base == target:
        raise ValueError("Catch-up allowed only from exact installed PROD Release 727")
    title = git(root, "log", "-1", "--format=%s", target)
    if not title.startswith("Release 735:"):
        raise ValueError("Catch-up requires the exact Release 735 target commit")
    chain = [base, *(sha for _, sha in MILESTONES), target]
    for previous, successor in zip(chain, chain[1:]):
        git(root, "merge-base", "--is-ancestor", previous, successor)
    if git(root, "show", f"{DEV_730}:app/models.py") != git(
        root, "show", f"{base}:app/models.py"
    ):
        raise ValueError("PROD 727 schema and verified DEV 730 schema differ")
    if git(root, "show", f"{SCHEMA_INTRO}:app/models.py") != git(
        root, "show", f"{target}:app/models.py"
    ):
        raise ValueError("Schema modified after reviewed Release 731")

    # There is one, and only one, schema-bearing file across the backlog.
    paths = set(git(root, "diff", "--name-only", base, target).splitlines())
    if "app/models.py" not in paths:
        raise ValueError("Expected additive tablet migration is missing")
    extra = {
        path for path in paths
        if path in SCHEMA_PATHS - {"app/models.py"}
        or path.startswith(("deploy/", "alembic/", "requirements"))
    }
    if extra:
        raise ValueError("Unreviewed schema or dependency changes in catch-up")

    # Reapply the original Release 731 exact-source schema proof against its
    # immutable first installation commit, not the later application changes.
    reviewer = root / "scripts/tracker_schema_review731.py"
    if (not reviewer.is_file() or reviewer.is_symlink() or
            reviewer.read_text() != git(
                root, "show", f"{SCHEMA_INTRO}:scripts/tracker_schema_review731.py"
            )):
        raise ValueError("Original Release 731 schema reviewer was modified")
    process = subprocess.run(
        [sys.executable, "-B", str(reviewer),
         "--root", str(root), "--base", base, "--target", SCHEMA_INTRO],
        capture_output=True, text=True, check=False,
    )
    if (process.returncode or
            "RELEASE_731_APPEND_ONLY_SCHEMA_REVIEW=PASSED" not in
            process.stdout.splitlines()):
        raise ValueError("Original exact 731 additive schema review failed")
    print("RELEASE_735_BACKLOG_729_734_ANCESTRY=PASSED")
    print("RELEASE_735_CATCHUP_SCHEMA_REVIEW=PASSED")
    print("RELEASE_735_REVIEWED_ADDITIVE_TABLES=2")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root, args.base, args.target)


if __name__ == "__main__":
    main()
