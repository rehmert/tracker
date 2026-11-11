#!/usr/bin/env python3
"""Read-only dependency and security readiness inventory for Tracker hosts.

Only package *names and versions* are reported. Never reads or prints secrets.
Does not install dependencies, change CSRF settings, or touch the database.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TRACKED = (
    "alembic", "fastapi", "httpx", "jinja2", "openpyxl",
    "pip", "playwright", "pytest", "pytest-xdist",
    "python-multipart", "sqlalchemy", "starlette", "uvicorn",
)


def package_versions(names=TRACKED):
    result = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = "NOT_INSTALLED"
    return result


def requirement_specs(root=ROOT):
    result = {}
    for filename in ("requirements.txt", "requirements-dev.txt"):
        path = root / filename
        requirements = []
        for line in path.read_text(encoding="utf-8").splitlines():
            cleaned = line.split("#", 1)[0].strip()
            if not cleaned or cleaned.startswith("-r "):
                continue
            requirements.append({
                "requirement": cleaned,
                "exact_pin": "==" in cleaned or "===" in cleaned,
            })
        result[filename] = requirements
    return result


def snapshot(instance: str):
    return {
        "instance": instance,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "packages": package_versions(),
        "requirements": requirement_specs(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", choices=("DEV", "PROD"), required=True)
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    parser.add_argument(
        "--security-audit", action="store_true",
        help="Also run the existing credential-redacting security audit",
    )
    args = parser.parse_args(argv)
    if args.json and args.security_audit:
        parser.error("Use --json and --security-audit separately")

    report = snapshot(args.instance)
    if args.json:
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0

    print(f"INSTANCE={args.instance}")
    print(f"PYTHON_VERSION={report['python']}")
    print(f"SQLITE_VERSION={report['sqlite']}")
    for name, value in sorted(report["packages"].items()):
        print(f"PACKAGE {name}={value}")
    for source, specs in report["requirements"].items():
        unpinned = sum(not spec["exact_pin"] for spec in specs)
        print(f"REQUIREMENTS {source} total={len(specs)} unpinned={unpinned}")
    print("DEPENDENCY_INVENTORY=COMPLETE")
    print("DEPENDENCY_LOCKFILE=NOT_ESTABLISHED")
    if args.security_audit:
        result = subprocess.run([
            sys.executable,
            str(ROOT / "scripts/tracker-security-audit536.py"),
            "--instance", args.instance,
        ], check=False)
        print(f"SECURITY_AUDIT_EXIT={result.returncode}")
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
