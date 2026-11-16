#!/usr/bin/env python3
"""Fail-closed evidence check for resuming Release 645 after backup failure.

The previously tested application and tests must be byte-identical to the
current candidate. Only approved release/diagnostic tooling may differ.
This does NOT issue a DEV qualification receipt; the release worker remains
responsible for a fresh validated backup, isolated restore, migration, runtime
smoke, and production-excluded DEV deployment.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

BASE = "5bc0894c2c2865856856298083ca21bc62d00069"
QUALIFIED = "0d4dbb1183d92f50676c29b42ac18578fe2be0f5"
ROOT = Path("/tmp/tracker-backups")
ALLOW_DIFF = frozenset({
    "scripts/tracker-coa-attachment-audit645.py",
    "scripts/tracker_schema_review645.py",
    "scripts/tracker-release.sh",
    "scripts/tracker-resume-evidence645.py",
    "scripts/tracker-coa-dev645.sh",
    "scripts/tracker-coa-preflight645.sh",
})
MARKERS = (
    "=== BROWSER GATE PASSED ===",
    "=== ALL BACKEND TESTS PASSED ===",
    "=== Verified database backup required for data migration ===",
    "ValueError: Backup contains 15 missing referenced attachment(s)",
    "EXIT_STATUS=1",
)


def fail(message: str):
    raise SystemExit("COA_645_RESUME_DENIED=" + message)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        fail("git verification failed: " + proc.stderr[:180])
    return proc.stdout.strip()


def _secure_regular(path: Path):
    if path.is_symlink() or not path.is_file():
        fail("invalid or symlinked evidence file")
    info = path.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
        fail("evidence log must be root-owned and private")
    if info.st_size > 15_000_000:
        fail("evidence log unexpectedly large")


def _verify_log(path: Path):
    parent = path.parent
    if (parent.parent != ROOT or not re.fullmatch(r"release\\.[A-Za-z0-9]{8}", parent.name)
            or parent.is_symlink() or not parent.is_dir()):
        fail("untrusted evidence directory")
    if parent.stat().st_uid != 0 or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        fail("evidence directory not private")
    _secure_regular(path)
    content = path.read_text(errors="replace")
    if (content.count("CANDIDATE_COMMIT=" + QUALIFIED) < 1
            or "instance: DEV" not in content
            or "COA_645_SCHEMA_PROCEDURE=AUTHORIZED" not in content
            or "QA_FULL_REQUIRED=1" not in content):
        fail("failed log does not identify expected fully qualified DEV candidate")
    for marker in MARKERS:
        if content.count(marker) != 1:
            fail("required qualification or backup-failure marker missing: " + marker)
    offsets = [content.index(marker) for marker in MARKERS]
    if offsets != sorted(offsets):
        fail("qualification and failure events out of order")
    if ("=== Install via fast-forward ===" in content
            or "TRACKER RELEASE DEPLOYMENT SUCCESS" in content
            or "EXIT_STATUS=0" in content):
        fail("previous attempt reached installation or success")
    return path


def verify(app: Path, qa: Path, base: str, target: str):
    if os.geteuid() != 0:
        fail("root required")
    if base != BASE or not re.fullmatch(r"[0-9a-f]{40}", target):
        fail("incorrect base or target")
    if git(app, "rev-parse", "HEAD") != BASE:
        fail("installed source is not expected Release 644 base")
    if git(qa, "rev-parse", "HEAD") != target:
        fail("candidate worktree mismatch")
    git(app, "merge-base", "--is-ancestor", QUALIFIED, target)
    changed = frozenset(git(app, "diff", "--name-only", QUALIFIED, target).splitlines())
    if not changed <= ALLOW_DIFF:
        fail("application, tests, or unapproved files changed since full qualification: " +
             ", ".join(sorted(changed - ALLOW_DIFF)))
    # Ensure prior qualified version actually exists locally.
    if git(app, "rev-parse", QUALIFIED + "^{commit}") != QUALIFIED:
        fail("previous qualified commit missing")
    logs = sorted(ROOT.glob("release.*/deployment.log"))
    valid = []
    for path in logs:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 15_000_000:
            continue
        # The quick filter only narrows candidates. Every matching log must
        # independently pass strict ownership, chronology and content checks.
        if "CANDIDATE_COMMIT=" + QUALIFIED in path.read_text(errors="replace"):
            valid.append(_verify_log(path))
    if len(valid) != 1:
        fail(f"expected exactly one verified prior attempt; got {len(valid)}")
    print("COA_645_RESUME_SOURCE_EVIDENCE=VERIFIED")
    print("COA_645_PRIOR_QUALIFIED_COMMIT=" + QUALIFIED)
    print("COA_645_CURRENT_CANDIDATE=" + target)
    print("COA_645_PRIOR_BROWSER_AND_BACKEND=PASSED")
    print("COA_645_ONLY_APPROVED_TOOLING_CHANGED=YES")
    print("COA_645_PRIOR_FAILURE=BACKUP_ONLY")
    print("COA_645_RESUME_EVIDENCE_LOG=" + str(valid[0]))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    verify(args.app.resolve(), args.qa.resolve(), args.base, args.target)


if __name__ == "__main__":
    main()
