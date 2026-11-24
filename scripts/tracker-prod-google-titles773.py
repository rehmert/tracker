#!/usr/bin/env python3
"""Release 773: exact source review and private one-table pre-migration backup.

The settings table does not alter any existing Tracker medication, supplement,
protocol or Google link tables. PROD must back up and restore-verify data before
the new metadata table can be created at application startup.
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

PROD_BASE = "47642b465b1cb98f40aab2ce68c6a7526394298d"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MODEL_PATH = "app/google_tasks_models769.py"
NEW_TABLE = "google_tasks_titles773"
OLD_CLASSES = (
    "GoogleTasksConnection769", "GoogleTasksList769",
    "GoogleTasksLink769", "GoogleTasksExclusion769",
)
OLD_TABLES = frozenset({
    "google_tasks_connection769", "google_tasks_lists769",
    "google_tasks_links769", "google_tasks_exclusions769",
})
ALLOWED_APP = frozenset({
    "app/google_tasks_models769.py",
    "app/google_tasks_projection769.py",
    "app/routers/google_tasks769.py",
    "app/templates/google_tasks769.html",
})


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        stderr=subprocess.PIPE, text=True,
    ).strip()


def _classes(source: str) -> dict[str, ast.ClassDef]:
    return {
        node.name: node for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef)
    }


def review_source(root: Path, base: str, target: str) -> None:
    """Validate the exact 772->773 additive scope and original model immutability."""
    if not SHA.fullmatch(base) or not SHA.fullmatch(target) or base != PROD_BASE:
        raise ValueError("Expected exact installed 772 baseline")
    if target == base:
        raise ValueError("Target cannot equal installed 772")
    git(root, "merge-base", "--is-ancestor", base, target)
    changes = set(git(root, "diff", "--name-only", base, target).splitlines())
    if {path for path in changes if path.startswith("app/")} != ALLOWED_APP:
        raise ValueError("Unexpected Tracker application changes in 773")
    if any(
        path.startswith(("deploy/", "requirements", "alembic/"))
        or path in ("alembic.ini", "app/db.py", "app/models.py", "app/migrations.py",
                    "app/main.py", "scripts/tracker-release.sh")
        for path in changes
    ):
        raise ValueError("Other schema, dependency or deployment changes are forbidden")
    if any(not path.startswith(("app/", "docs/", "scripts/", "tests/"))
           for path in changes):
        raise ValueError("Unexpected source outside reviewed directories")
    old = _classes(git(root, "show", f"{base}:{MODEL_PATH}"))
    new = _classes(git(root, "show", f"{target}:{MODEL_PATH}"))
    if set(new) != set(old) | {"GoogleTasksTitle773"}:
        raise ValueError("Unexpected model classes in Google Tasks schema")
    for cls in OLD_CLASSES:
        if ast.dump(old[cls], include_attributes=False) != ast.dump(
                new[cls], include_attributes=False):
            raise ValueError("Existing Google Tasks schema model changed: " + cls)
    added = new["GoogleTasksTitle773"]
    tablenames = [
        node.value.value
        for node in added.body
        if isinstance(node, ast.Assign)
        and any(isinstance(key, ast.Name) and key.id == "__tablename__"
                for key in node.targets)
        and isinstance(node.value, ast.Constant)
    ]
    columns = [
        node.target.id for node in added.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]
    if tablenames != [NEW_TABLE] or columns != ["id","kind","source_id","title"]:
        raise ValueError("Title 773 table structure changed")
    text = git(root, "show", f"{target}:{MODEL_PATH}")
    if ('UniqueConstraint("kind", "source_id", name="uq_google_tasks_title_source773")'
            not in text or 'title: Mapped[str] = mapped_column(String(80)' not in text):
        raise ValueError("Missing unique source identity or 80-character title cap")
    main = git(root, "show", f"{target}:app/main.py")
    if ("from . import google_tasks_models769" not in main
            or "Base.metadata.create_all(engine)" not in main):
        raise ValueError("New table is not registered for additive startup creation")
    projection = git(root, "show", f"{target}:app/google_tasks_projection769.py")
    if ('_key("protocol", item.id, day, clock)' not in projection
            or '_key(item.kind, schedule.id, day, clock)' not in projection):
        raise ValueError("Google task identities are not preserved")


def resolve_data_dir(root: Path, env: Path) -> Path:
    if not env.is_file() or env.is_symlink():
        raise ValueError("Private Tracker environment unavailable")
    path = root / "data"
    for line in env.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$", line)
        if match and match.group(1).strip():
            path = Path(match.group(1).strip().strip(chr(34) + chr(39)))
    if not path.is_absolute():
        path = root / path
    if path.is_symlink():
        raise ValueError("Linked data directory not allowed")
    path = path.resolve()
    db = path / "tracker.db"
    if path == Path("/") or not path.is_dir() or not db.is_file() or db.is_symlink():
        raise ValueError("Tracker data or database invalid")
    return path


def verify_schema_before(data: Path) -> None:
    """Reject replay and preserve the four existing Google sync state tables."""
    with sqlite3.connect((data / "tracker.db").as_uri()+"?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Tracker SQLite integrity failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Tracker SQLite foreign key check failed")
        present = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if NEW_TABLE in present:
            raise ValueError("Custom Google title table already exists")
        if not OLD_TABLES.issubset(present):
            raise ValueError("Missing expected Release 769 Google Tasks tables")


def run_verified(root: Path, base: str, target: str) -> None:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-prod":
        raise ValueError("PROD-only schema snapshot guard")
    if root != Path("/opt/tracker") or root.is_symlink():
        raise ValueError("Unexpected production app checkout")
    review_source(root, base, target)
    if (git(root, "rev-parse", "HEAD") != base
            or git(root, "branch", "--show-current") != "main"
            or git(root, "status", "--porcelain")):
        raise ValueError("Production checkout is not exact clean Release 772")
    data = resolve_data_dir(root, Path("/etc/tracker.env"))
    verify_schema_before(data)
    attachment_gate = root / "scripts/tracker-attachment-integrity645.py"
    if not attachment_gate.is_file() or attachment_gate.is_symlink():
        raise ValueError("Attachment integrity checker missing")
    subprocess.run(
        [sys.executable, str(attachment_gate), "--data", str(data), "--hashes"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
    )
    print("RELEASE_773_PROD_UPLOAD_GATE=PASSED", flush=True)
    destination = root / "backups/release773-prod-preinstall"
    if destination.is_symlink():
        raise ValueError("Unsafe backup location")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    from app.backup import create_backup, verify_backup
    archive = create_backup(data, destination)
    if archive.is_symlink() or not archive.is_file() or archive.parent != destination:
        raise ValueError("Backup archive outside trusted location")
    archive.chmod(0o600)
    verify_backup(archive)
    verifier = root / "scripts/tracker-restore-verify.py"
    if not verifier.is_file() or verifier.is_symlink():
        raise ValueError("Existing isolated restore verifier missing")
    subprocess.run(
        [sys.executable, str(verifier), "--archive", str(archive)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900,
    )
    print("RELEASE_773_PROD_ARCHIVE_RESTORED=PASSED", flush=True)
    archives = sorted(destination.glob("tracker-*.zip"), reverse=True)
    for old in archives[10:]:
        if old.is_symlink() or not old.is_file():
            raise ValueError("Backup retention contains unsafe link")
        old.unlink()
    print("RELEASE_773_PROD_DB_SNAPSHOT=VERIFIED", flush=True)


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
        print("RELEASE_773_PROD_SCHEMA_BACKUP=BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
