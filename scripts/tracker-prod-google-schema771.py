#!/usr/bin/env python3
"""Release 771: immutable 768->771 Google Tasks PROD schema and backup barrier.

Executed by the signed PROD remote runner before touching installed source.
Synthetic tests invoke review_source only; never open real Tracker data.
"""
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

PROD_BASE = "62a78b4f0b79f2f6762976c1231cab2f5f593f25"
DEV_770 = "a236ef996c725a231b6420ebf41dd63bf506e8bc"
SHA = re.compile(r"[0-9a-f]{40}\Z")
SOURCE = "app/google_tasks_models769.py"
EXPECTED_TABLES = {
    "GoogleTasksConnection769": "google_tasks_connection769",
    "GoogleTasksList769": "google_tasks_lists769",
    "GoogleTasksLink769": "google_tasks_links769",
    "GoogleTasksExclusion769": "google_tasks_exclusions769",
}
ALLOWED_APPLICATION_PATHS = frozenset({
    "app/google_tasks_background769.py", "app/google_tasks_client769.py",
    "app/google_tasks_models769.py", "app/google_tasks_projection769.py",
    "app/google_tasks_sync769.py", "app/main.py",
    "app/routers/google_tasks769.py", "app/templates/google_tasks769.html",
    "app/templates/protocols.html", "app/templates/regimen635.html",
})


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        stderr=subprocess.PIPE, text=True,
    ).strip()


def review_source(root: Path, base: str, target: str) -> None:
    """Verify exactly four already-DEV-qualified additive Google Tasks tables."""
    if not SHA.fullmatch(base) or not SHA.fullmatch(target) or base != PROD_BASE:
        raise ValueError("Exact installed PROD 768 baseline required")
    if target in (base, DEV_770):
        raise ValueError("A new, distinct Release 771 target is required")
    git(root, "merge-base", "--is-ancestor", base, target)
    git(root, "merge-base", "--is-ancestor", DEV_770, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    changed_app = {p for p in changed if p.startswith("app/")}
    if changed_app != ALLOWED_APPLICATION_PATHS:
        raise ValueError("Unreviewed application path in Google Tasks catch-up")
    if any(p.startswith(("deploy/", "requirements", "alembic/"))
           or p in ("alembic.ini", "app/db.py", "app/models.py",
                    "app/migrations.py") for p in changed):
        raise ValueError("Other schema, dependency or deployment changes forbidden")
    # This release may add only operations/tests/docs, never change any already
    # qualified runtime application behavior.
    for path in ALLOWED_APPLICATION_PATHS:
        if git(root, "rev-parse", f"{DEV_770}:{path}") != git(
                root, "rev-parse", f"{target}:{path}"):
            raise ValueError("Qualified Google Tasks application file changed")
    source = git(root, "show", f"{target}:{SOURCE}")
    tree = ast.parse(source, filename=SOURCE)
    observed = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for assignment in node.body:
            if isinstance(assignment, ast.Assign) and any(
                    isinstance(key, ast.Name) and key.id == "__tablename__"
                    for key in assignment.targets):
                if not isinstance(assignment.value, ast.Constant):
                    raise ValueError("Unexpected dynamic schema table")
                observed[node.name] = assignment.value.value
    if observed != EXPECTED_TABLES:
        raise ValueError("Google Tasks schema is not exactly four reviewed tables")
    main = git(root, "show", f"{target}:app/main.py")
    if ("from . import google_tasks_models769" not in main
            or "Base.metadata.create_all(engine)" not in main):
        raise ValueError("Google Tasks table registration absent")
    client = git(root, "show", f"{target}:app/google_tasks_client769.py")
    if ("def require_production770()" not in client
            or 'config.instance_label() != "PROD"' not in client):
        raise ValueError("PROD-only Google network guard missing")


def live_data_dir(root: Path, env: Path) -> Path:
    """Match Tracker service working directory and reject linked data."""
    if not env.is_file() or env.is_symlink():
        raise ValueError("Trusted PROD environment missing")
    path = root / "data"
    for line in env.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$", line)
        if match and match.group(1).strip():
            path = Path(match.group(1).strip().strip("\"'"))
    if not path.is_absolute():
        path = root / path
    if path.is_symlink():
        raise ValueError("Unsafe live data symlink")
    path = path.resolve()
    db = path / "tracker.db"
    if path == Path("/") or not path.is_dir() or not db.is_file() or db.is_symlink():
        raise ValueError("Live database missing or linked")
    return path


def verify_database(path: Path) -> None:
    with sqlite3.connect((path / "tracker.db").as_uri() + "?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign key check failed")
        existing = set(row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))
        if existing.intersection(EXPECTED_TABLES.values()):
            raise ValueError("Google Tasks tables unexpectedly preexisting on PROD")


def run_verified(root: Path, base: str, target: str) -> None:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-prod":
        raise ValueError("PROD root-only pre-install schema backup")
    if root != Path("/opt/tracker") or root.is_symlink():
        raise ValueError("Unexpected PROD app root")
    review_source(root, base, target)
    if (git(root, "rev-parse", "HEAD") != base
            or git(root, "branch", "--show-current") != "main"
            or git(root, "status", "--porcelain")):
        raise ValueError("Installed PROD source differs from exact clean 768")
    data = live_data_dir(root, Path("/etc/tracker.env"))
    verify_database(data)
    gate = root / "scripts/tracker-attachment-integrity645.py"
    if not gate.is_file() or gate.is_symlink():
        raise ValueError("Installed upload integrity checker unavailable")
    subprocess.run(
        [sys.executable, str(gate), "--data", str(data), "--hashes"],
        check=True, capture_output=True, timeout=600,
    )
    print("RELEASE_771_PROD_UPLOAD_CHECK=PASSED", flush=True)
    destination = root / "backups/release771-prod-preinstall"
    if destination.is_symlink():
        raise ValueError("Unsafe backup destination")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    from app.backup import create_backup, verify_backup
    archive = create_backup(data, destination)
    if archive.is_symlink() or not archive.is_file() or archive.parent != destination:
        raise ValueError("Backup path invalid")
    archive.chmod(0o600)
    verify_backup(archive)
    verifier = root / "scripts/tracker-restore-verify.py"
    if not verifier.is_file() or verifier.is_symlink():
        raise ValueError("Installed restore verifier unavailable")
    subprocess.run(
        [sys.executable, str(verifier), "--archive", str(archive)],
        check=True, capture_output=True, timeout=900,
    )
    print("RELEASE_771_PROD_RESTORE_CHECK=PASSED", flush=True)
    archives = sorted(destination.glob("tracker-*.zip"), reverse=True)
    for old in archives[10:]:
        if old.is_symlink() or not old.is_file():
            raise ValueError("Unsafe backup archive in retention set")
        old.unlink()
    print("RELEASE_771_PROD_BACKUP=VERIFIED", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    try:
        run_verified(args.app, args.base, args.target)
    except (ValueError, OSError, sqlite3.Error, SyntaxError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("RELEASE_771_PROD_SCHEMA_BACKUP=BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
