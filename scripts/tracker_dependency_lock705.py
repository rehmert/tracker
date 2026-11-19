#!/usr/bin/env python3
"""Release 705: hash-lock trusted local wheel bytes, without installs/downloads.

Does not assert browser/OS reproducibility or authorize a live environment change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from packaging.utils import parse_wheel_filename
from scripts.tracker_dependency_baseline569 import (
    BASELINE, CONSTRAINTS, canonical, read_manifest, read_constraints,
    validate_constraints,
)

LOCK_NAME = "tracker-python-wheels705.json"
REQUIREMENTS_NAME = "requirements-hashes705.txt"


class LockError(ValueError):
    pass


def all_pins() -> dict[str, str]:
    baseline = read_manifest(BASELINE)
    validate_constraints(baseline, read_constraints(CONSTRAINTS))
    return baseline["packages"]


def private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise LockError("Required mode-0700 private output directory unavailable")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(wheelhouse: Path, pins: dict[str, str]) -> list[dict]:
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise LockError("Wheelhouse missing or unsafe")
    found = {}
    for wheel in sorted(wheelhouse.iterdir()):
        if wheel.is_symlink() or not wheel.is_file() or wheel.suffix != ".whl":
            raise LockError("Wheelhouse contains a non-wheel or symlink")
        name, version, _build, _tags = parse_wheel_filename(wheel.name)
        name = canonical(str(name))
        if name in found:
            raise LockError("Multiple wheels for one package")
        if pins.get(name) != str(version):
            raise LockError("Wheel name/version differs from the approved pins")
        found[name] = {
            "name": name,
            "version": str(version),
            "filename": wheel.name,
            "sha256": digest(wheel),
            "bytes": wheel.stat().st_size,
        }
    if set(found) != set(pins):
        raise LockError("Wheelhouse does not contain exactly the expected packages")
    return [found[name] for name in sorted(found)]


def requirements(rows: list[dict]) -> str:
    return (
        "# Release 705: hash-locked bytes for a disposable OFFLINE install only.\n"
        "# pip install --no-index --only-binary=:all: --require-hashes "
        "--find-links WHEELHOUSE -r requirements-hashes705.txt\n"
        + "".join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n"
                  for r in rows)
    )


def create(wheelhouse: Path, output: Path) -> dict:
    private_directory(output)
    rows = inventory(wheelhouse, all_pins())
    report = {
        "schema_version": 1,
        "source_baseline": "Release 569 Python 3.13.5 observed versions",
        "scope": "Python wheels only; browser, OS, replay and rollback not certified",
        "wheels": rows,
    }
    items = (
        (LOCK_NAME, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()),
        (REQUIREMENTS_NAME, requirements(rows).encode()),
    )
    for name, content in items:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(output / name, flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    return report


def verify(wheelhouse: Path, output: Path) -> dict:
    private_directory(output)
    for filename in (LOCK_NAME, REQUIREMENTS_NAME):
        path = output / filename
        if path.is_symlink() or not path.is_file():
            raise LockError("Artifact receipt is not a regular file")
    report = json.loads((output / LOCK_NAME).read_text(encoding="utf-8"))
    if (not isinstance(report, dict)
            or set(report) != {"schema_version", "source_baseline", "scope", "wheels"}
            or report["schema_version"] != 1):
        raise LockError("Invalid wheel artifact manifest")
    rows = inventory(wheelhouse, all_pins())
    if report["wheels"] != rows:
        raise LockError("Wheelhouse changed since lock creation")
    if (output / REQUIREMENTS_NAME).read_text(encoding="utf-8") != requirements(rows):
        raise LockError("Hash requirements and wheel manifest disagree")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (create if args.create else verify)(args.wheelhouse, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"DEPENDENCY_705_WHEEL_LOCK=FAILED ({type(exc).__name__})",
              file=sys.stderr)
        return 1
    print("DEPENDENCY_705_WHEEL_COUNT=" + str(len(result["wheels"])))
    print("DEPENDENCY_705_WHEEL_LOCK=CREATED" if args.create
          else "DEPENDENCY_705_WHEEL_LOCK=VERIFIED")
    print("DEPENDENCY_705_FRESH_REPLAY=NOT_CERTIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
