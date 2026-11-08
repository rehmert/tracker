#!/usr/bin/env python3
"""Fail-closed permission gate for installing Tracker application source.

Run after installing a release, before restarting Tracker. No file changes,
DB access, or network operations. Checks the effective systemd service user,
not merely root readability.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALWAYS_CHECK = (
    "app/main.py",
    "app/templates/base.html",
    "app/routers/reliability.py",
    "app/routers/maintenance_review.py",
)


def _run(command):
    return subprocess.run(
        command, text=True, capture_output=True, check=False
    )


def service_user(name):
    process = _run([
        "systemctl", "show", name,
        "--property=User", "--value",
    ])
    if process.returncode:
        raise ValueError(
            f"Cannot inspect service {name}: "
            f"{process.stderr.strip()[:180]}"
        )
    # systemd's empty User means the unit runs as root.
    return process.stdout.strip() or "root"


def changed_paths(root, base, target):
    process = _run([
        "git", "-c", f"safe.directory={root}", "-C", str(root),
        "diff", "--name-only", "--diff-filter=ACMR",
        base, target, "--", "app/",
    ])
    if process.returncode:
        raise ValueError(
            "Cannot inspect release changes: "
            + process.stderr.strip()[:180]
        )
    return [
        line for line in process.stdout.splitlines()
        if line.strip()
    ]



def tracked_app_paths(root):
    """Check every tracked application file, not only release diff files.

    A restrictive checkout umask can make previously unchanged modules
    unreadable, and importing the app will then fail at service restart.
    """
    process = subprocess.run(
        [
            "git", "-c", f"safe.directory={root}", "-C", str(root),
            "ls-files", "-z", "--", "app/",
        ],
        capture_output=True, check=False,
    )
    if process.returncode:
        raise ValueError(
            "Cannot list tracked application files: "
            + process.stderr.decode("utf-8", "replace")[:180]
        )
    names = [os.fsdecode(raw) for raw in process.stdout.split(b"\0") if raw]
    if not names:
        raise ValueError("No tracked application files found")
    return names


def source_paths(root, changes):
    """Only regular files under the application source tree are allowed."""
    root = Path(root).resolve()
    paths = []
    errors = []
    for name in sorted(set(ALWAYS_CHECK) | set(changes)):
        rel = Path(name)
        if (
            rel.is_absolute()
            or ".." in rel.parts
            or not rel.parts
            or rel.parts[0] != "app"
        ):
            errors.append(f"unsafe path: {name}")
            continue
        path = root / rel
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing or symlinked source: {name}")
            continue
        paths.append((name, path))
    return paths, errors


def can_read(path, user):
    """Check effective OS access, including every parent directory."""
    if user == "root":
        return path.is_file()
    result = _run(["runuser", "-u", user, "--", "test", "-r", str(path)])
    return result.returncode == 0


def validate(root, changes, user, probe=can_read):
    paths, errors = source_paths(root, changes)
    for name, path in paths:
        if not probe(path, user):
            errors.append(f"service user {user} cannot read {name}")
    return len(paths), errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base", required=True, help="Installed base SHA")
    parser.add_argument("--target", required=True, help="Release target SHA")
    parser.add_argument("--service", default="tracker")
    parser.add_argument(
        "--service-user",
        help="Explicit OS user (normally obtained from systemd)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        user = args.service_user or service_user(args.service)
        changed = changed_paths(root, args.base, args.target)
        tracked = tracked_app_paths(root)
        count, errors = validate(root, changed + tracked, user)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if errors:
        for issue in errors:
            print(f"FAIL: {issue}", file=sys.stderr)
        return 1

    print(
        f"PASS: {count} application files readable by "
        f"{user} ({len(changed)} changed application paths; all tracked files checked)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
