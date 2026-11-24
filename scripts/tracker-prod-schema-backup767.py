#!/usr/bin/env python3
"""Release 767 strict PROD pre-install backup for exact 765 -> 766+767 catch-up.

Source-review and backup code are extracted from the signed target Git blob.
This is a separate strict backup before the current shared runner, whose
legacy schema matcher does not yet recognize independent device_models766.
No application data, credentials or archives are sent to GitHub.
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

PROD_765 = "8c67580611fd945d9ae83f8015f071a24ab6fee5"
APPROVED_DEV_766 = "45263b9659232b6ac6a922da38599f92842a32d8"
SHA = re.compile(r"[0-9a-f]{40}\Z")
SCHEMA_SOURCE = "app/device_models766.py"
MODEL_TABLE = "device_days766"


def git(root: Path, *args: str) -> str:
    cmd = ["git", "-c", f"safe.directory={root}", "-C", str(root), *args]
    return subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE).strip()


def review_source(root: Path, base: str, target: str) -> None:
    """Pure read-only source proof. Safe in an isolated test worktree."""
    if not SHA.fullmatch(base) or not SHA.fullmatch(target):
        raise ValueError("Exact lowercase SHAs required")
    if base != PROD_765 or target in (base, APPROVED_DEV_766):
        raise ValueError("Release 767 is restricted to the PROD 765 catch-up")
    git(root, "merge-base", "--is-ancestor", base, target)
    git(root, "merge-base", "--is-ancestor", APPROVED_DEV_766, target)
    incremental = set(
        git(root, "diff", "--name-only", APPROVED_DEV_766, target).splitlines()
    )
    # 767 may only repair the release process; never change qualified app
    # behavior or any test fixtures from the installed 766 candidate.
    if any(not path.startswith(("scripts/", "tests/", "docs/"))
           for path in incremental):
        raise ValueError("Release 767 contains a new application change")
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if SCHEMA_SOURCE not in changed or "app/main.py" not in changed:
        raise ValueError("Unreviewed device table introduction")
    for path in changed:
        if path in ("app/models.py", "app/migrations.py", "app/db.py") or (
            path.startswith("app/") and
            (path.endswith("_models.py")
             or path.startswith(("app/workout_models", "app/progress_models")))
        ):
            raise ValueError("Additional unreviewed model change: " + path)
    for path in (
        SCHEMA_SOURCE, "app/main.py", "app/routers/device_import766.py",
        "app/routers/food_recipes766.py",
    ):
        if git(root, "rev-parse", f"{APPROVED_DEV_766}:{path}") != git(
                root, "rev-parse", f"{target}:{path}"):
            raise ValueError("Unreviewed changes to DEV-qualified schema code")
    source = git(root, "show", f"{target}:{SCHEMA_SOURCE}")
    tree = ast.parse(source, filename=SCHEMA_SOURCE)
    tables = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for assignment in node.body:
                if isinstance(assignment, ast.Assign):
                    if any(isinstance(t, ast.Name) and t.id == "__tablename__"
                           for t in assignment.targets):
                        if not isinstance(assignment.value, ast.Constant):
                            raise ValueError("Dynamic table name not approved")
                        tables.append((node.name, assignment.value.value))
    if tables != [("DeviceDay766", MODEL_TABLE)]:
        raise ValueError("Unexpected device model/table declarations")
    main = git(root, "show", f"{target}:app/main.py")
    if ("from . import device_models766" not in main
            or "Base.metadata.create_all(engine)" not in main):
        raise ValueError("Device table registration or startup creation absent")


def resolve_data_dir768(root: Path, env: Path) -> Path:
    """Resolve exactly as the Tracker service resolves TRACKER_DATA_DIR.

    In particular, a relative value is relative to WorkingDirectory
    (/opt/tracker), not the Python script's temporary staging directory.
    Do not allow a symlink for the resulting live database or data directory.
    """
    if not env.is_file() or env.is_symlink():
        raise ValueError("Trusted environment file unavailable")
    path = root / "data"
    for line in env.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$", line)
        if match and match.group(1).strip():
            path = Path(match.group(1).strip().strip("\"'"))
    # Match the service's WorkingDirectory=/opt/tracker. Tracker's
    # config uses Path(...).resolve() after resolving the process CWD.
    if not path.is_absolute():
        path = root / path
    if path.is_symlink():
        raise ValueError("Live Tracker data directory may not be symlinked")
    path = path.resolve()
    database = path / "tracker.db"
    if path == Path("/") or not path.is_dir() or not database.is_file():
        raise ValueError("Live Tracker SQLite database missing")
    if database.is_symlink():
        raise ValueError("Live database may not be symlinked")
    return path


def live_data_dir() -> Path:
    return resolve_data_dir768(Path("/opt/tracker"), Path("/etc/tracker.env"))


def verify_pre_schema_database(path: Path) -> None:
    with sqlite3.connect((path/"tracker.db").as_uri()+"?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Live SQLite integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Live SQLite foreign-key consistency check failed")
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (MODEL_TABLE,),
        ).fetchone() is not None:
            raise ValueError("Device table already exists on PROD 765")


def run_verified(app: Path, base: str, target: str) -> None:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-prod":
        raise ValueError("Strict pre-migration backup is restricted to root on tracker-prod")
    if app != Path("/opt/tracker") or app.is_symlink():
        raise ValueError("Unexpected PROD application checkout")
    review_source(app, base, target)
    if git(app, "rev-parse", "HEAD") != base:
        raise ValueError("PROD source changed before schema snapshot")
    if git(app, "branch", "--show-current") != "main":
        raise ValueError("PROD must be on main")
    if git(app, "status", "--porcelain"):
        raise ValueError("PROD working tree is not clean")
    data = live_data_dir()
    verify_pre_schema_database(data)
    gate = app / "scripts/tracker-attachment-integrity645.py"
    if not gate.is_file() or gate.is_symlink():
        raise ValueError("Trusted present-upload gate missing")
    subprocess.run(
        [sys.executable, str(gate), "--data", str(data), "--hashes"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    print("RELEASE_767_PROD_ATTACHMENT_GATE=PASSED", flush=True)
    destination = app / "backups/release767-prod-preinstall"
    if destination.is_symlink():
        raise ValueError("Backup destination is a symlink")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    from app.backup import create_backup, verify_backup
    archive = create_backup(data, destination)
    if archive.is_symlink() or not archive.is_file() or archive.parent != destination:
        raise ValueError("Verified backup created outside protected destination")
    archive.chmod(0o600)
    verify_backup(archive)
    verifier = app / "scripts/tracker-restore-verify.py"
    if not verifier.is_file() or verifier.is_symlink():
        raise ValueError("Trusted isolated restore checker missing")
    subprocess.run(
        [sys.executable, str(verifier), "--archive", str(archive)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    print("RELEASE_767_PROD_SQLITE_UPLOAD_RESTORE=PASSED", flush=True)
    archives = sorted(destination.glob("tracker-*.zip"), reverse=True)
    for old in archives[10:]:
        if old.is_symlink() or not old.is_file():
            raise ValueError("Unsafe historical backup archive encountered")
        old.unlink()
    print("RELEASE_767_PROD_DATABASE_SNAPSHOT=VERIFIED", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    try:
        run_verified(args.app, args.base, args.target)
    except (ValueError, OSError, subprocess.CalledProcessError,
            sqlite3.Error, SyntaxError) as exc:
        print("RELEASE_767_PROD_SCHEMA_BACKUP=BLOCKED", file=sys.stderr)
        print("RELEASE_767_GUARD_FAILURE=" + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
