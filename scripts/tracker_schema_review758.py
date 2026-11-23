#!/usr/bin/env python3
"""Release 758 read-only exact additive manufacturing-date schema review.

Verify only a nullable ORM field and one SQLite migration declaration were
added to schema source. No existing data, schemas, or files are modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
MODEL_LINE = '    production_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # actual documented manufacture date, never inferred\n'
MIGRATION_LINE = '                "production_on": "DATE",  # Release 758: nullable documented manufacture date\n'


def exact_additive(before: str, after: str, added: str) -> bool:
    return after.count(added) == 1 and after.replace(added, "", 1) == before


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ValueError("Git source review failed")
    return proc.stdout


def review(root: Path, base: str, target: str) -> None:
    if not SHA.fullmatch(base) or not SHA.fullmatch(target) or base == target:
        raise ValueError("Distinct exact full base/target SHAs required")
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Worktree differs from pinned target")
    git(root, "merge-base", "--is-ancestor", base, target)
    for path, added in (
        ("app/models.py", MODEL_LINE),
        ("app/migrations.py", MIGRATION_LINE),
    ):
        previous = git(root, "show", f"{base}:{path}")
        current = git(root, "show", f"{target}:{path}")
        if not exact_additive(previous, current, added):
            raise ValueError("Unreviewed schema change in " + path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    try:
        review(args.root, args.base, args.target)
    except (ValueError, OSError) as exc:
        print("RELEASE_758_SCHEMA_REVIEW=BLOCKED_" + str(exc), file=sys.stderr)
        return 2
    print("RELEASE_758_SCHEMA_REVIEW=PASSED_EXACT_NULLABLE_ADDITION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
