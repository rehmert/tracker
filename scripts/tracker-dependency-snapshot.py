"""Read-only dependency snapshot/diff for isolated Tracker DEV/PROD LXCs.

Does not call pip, network, or package installers. Never prints environment
variables, credentials, package locations, or repository URL origins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "alembic", "fastapi", "httpcore", "httpx", "jinja2", "openpyxl",
    "pydantic", "pytest", "pytest-xdist", "python-multipart",
    "sqlalchemy", "starlette", "uvicorn",
)


def _digest(path: Path):
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root=ROOT):
    root = Path(root)
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "schema": 1,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "packages": packages,
        "requirements_sha256": {
            name: _digest(root / name)
            for name in ("requirements.txt", "requirements-dev.txt")
        },
    }


def compare_snapshots(first, second):
    """Return only differences that affect deployed package reproducibility."""
    differences = {}
    for key in ("python_version", "python_implementation"):
        if first.get(key) != second.get(key):
            differences[key] = [first.get(key), second.get(key)]
    for block in ("packages", "requirements_sha256"):
        before, after = first.get(block, {}), second.get(block, {})
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                differences[f"{block}.{key}"] = [before.get(key), after.get(key)]
    return differences


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Tracker dependency inventory/diff for LXC qualification"
    )
    parser.add_argument("--output", type=Path, help="Optional JSON snapshot file")
    parser.add_argument("--compare", type=Path, help="Compare against saved snapshot")
    args = parser.parse_args()
    report = snapshot()
    if args.compare:
        previous = json.loads(args.compare.read_text(encoding="utf-8"))
        report["differences"] = compare_snapshots(previous, report)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        import os
        import tempfile

        destination = args.output.absolute()
        # Never overwrite source or credentials; the operator chooses output.
        with tempfile.NamedTemporaryFile(
            mode="w", dir=destination.parent, prefix=".tracker-deps-",
            suffix=".json", encoding="utf-8", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        print(f"Snapshot: {destination}")
    else:
        print(payload, end="")
    return 2 if report.get("differences") else 0


if __name__ == "__main__":
    raise SystemExit(main())
