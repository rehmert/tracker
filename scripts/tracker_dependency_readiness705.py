#!/usr/bin/env python3
"""Release 705: read-only DEV Python and offline-wheel readiness audit.

No installs, upgrades, downloads, extracts, service operations or app DB access.
Passing this inspection does NOT approve wheel provenance or reconstructability.
"""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import Parser
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import sqlite3
import stat
import subprocess
import sys
import zipfile

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags, parse_tag
from packaging.utils import parse_wheel_filename

from scripts import tracker_dependency_baseline569 as baseline
from scripts import tracker_dependency_lock705 as lock

MAX_UNCOMPRESSED_WHEEL = 512 * 1024 * 1024


class ReadinessError(ValueError):
    pass


def runtime_audit() -> tuple[list[str], bool]:
    observed = baseline.read_manifest(baseline.BASELINE)
    pins = lock.all_pins()
    if len(pins) != 44 or len(observed["packages"]) != 44:
        raise ReadinessError("Changed Release 569 package baseline")
    actual = baseline.pip_packages()
    drift = baseline.compare(
        observed, actual, platform.python_version(), sqlite3.sqlite_version
    )
    # pip check is read-only. Force no-index, no-cache, no user site and
    # a bounded subprocess. No package resolver/install command is called.
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/nonexistent",
        "PIP_NO_INDEX": "1",
        "PIP_NO_CACHE_DIR": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
    }
    check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        env=environment, capture_output=True, text=True,
        check=False, timeout=45,
    )
    print(f"DEPENDENCY_705_PYTHON={platform.python_version()}")
    print(f"DEPENDENCY_705_SQLITE={sqlite3.sqlite_version}")
    print(f"DEPENDENCY_705_PLATFORM={platform.system()}-{platform.machine()}")
    print(f"DEPENDENCY_705_PINS={len(pins)}")
    print(f"DEPENDENCY_705_INSTALLED_PACKAGES={len(actual)}")
    for finding in drift:
        print(f"DEPENDENCY_705_DRIFT: {finding}")
    print(f"DEPENDENCY_705_DRIFT_COUNT={len(drift)}")
    print(f"DEPENDENCY_705_PIP_CHECK={'PASSED' if check.returncode == 0 else 'FAILED'}")
    return drift, check.returncode == 0


def safe_wheelhouse(path: Path) -> None:
    if not path.is_absolute():
        raise ReadinessError("Wheelhouse must be an absolute /tmp path")
    if path.is_symlink() or not path.is_dir():
        raise ReadinessError("Wheelhouse must be a real directory")
    if path.stat().st_mode & 0o077:
        raise ReadinessError("Wheelhouse must be private mode 0700")
    if not path.resolve().is_relative_to(Path("/tmp")):
        raise ReadinessError("Only an explicitly staged /tmp wheelhouse may be inspected")
    # Avoid trusting paths through symlinked intermediate directories.
    cursor = path
    while cursor != Path("/tmp"):
        if cursor.is_symlink():
            raise ReadinessError("Wheelhouse path contains a symlink")
        cursor = cursor.parent
    if cursor.is_symlink():
        raise ReadinessError("Temporary directory is symlinked")


def _sha256(stream) -> str:
    hasher = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        hasher.update(chunk)
    return base64.urlsafe_b64encode(hasher.digest()).rstrip(b"=").decode("ascii")


def audit_wheel(path: Path, pins: dict[str, str], supported: set) -> None:
    distribution, version, _build, filename_tags = parse_wheel_filename(path.name)
    name = baseline.canonical(str(distribution))
    if pins.get(name) != str(version):
        raise ReadinessError("Wheel filename is not in the observed pinset")
    if not filename_tags.intersection(supported):
        raise ReadinessError(f"Incompatible wheel tag for {name}")

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            files = {}
            for info in infos:
                part = PurePosixPath(info.filename)
                if (info.filename.startswith("/") or "\\" in info.filename
                        or ".." in part.parts or not info.filename
                        or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ReadinessError(f"Unsafe wheel archive member: {name}")
                if info.is_dir():
                    continue
                if info.filename in files:
                    raise ReadinessError(f"Duplicate wheel archive member: {name}")
                files[info.filename] = info
            if sum(info.file_size for info in files.values()) > MAX_UNCOMPRESSED_WHEEL:
                raise ReadinessError(f"Oversized wheel archive: {name}")
            metadata_paths = [key for key in files
                              if key.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ReadinessError(f"Missing or ambiguous wheel metadata: {name}")
            prefix = metadata_paths[0].removesuffix("METADATA")
            wheel_path = prefix + "WHEEL"
            record_path = prefix + "RECORD"
            if wheel_path not in files or record_path not in files:
                raise ReadinessError(f"Wheel metadata or RECORD missing: {name}")
            meta = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
            wheel = Parser().parsestr(archive.read(wheel_path).decode("utf-8"))
            if (baseline.canonical(meta.get("Name", "")) != name
                    or meta.get("Version") != pins[name]):
                raise ReadinessError(f"Internal wheel metadata disagrees: {name}")
            tags = set()
            for text in wheel.get_all("Tag", []):
                tags.update(parse_tag(text))
            if not tags or not filename_tags.issubset(tags):
                raise ReadinessError(f"Wheel WHEEL tags disagree with filename: {name}")
            py_constraint = meta.get("Requires-Python")
            if py_constraint and not SpecifierSet(py_constraint).contains(
                    platform.python_version(), prereleases=True):
                raise ReadinessError(f"Unsupported Python requirement: {name}")
            for dependency in meta.get_all("Requires-Dist", []):
                requirement = Requirement(dependency)
                if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                    continue
                dep_name = baseline.canonical(requirement.name)
                pinned = pins.get(dep_name)
                if pinned is None or (requirement.specifier
                                      and not requirement.specifier.contains(
                                          pinned, prereleases=True)):
                    raise ReadinessError(f"Unsatisfied wheel dependency: {name} -> {dep_name}")

            receipt = archive.read(record_path).decode("utf-8")
            recorded = {}
            for row in csv.reader(io.StringIO(receipt)):
                if len(row) != 3 or row[0] in recorded:
                    raise ReadinessError(f"Invalid wheel RECORD row: {name}")
                recorded[row[0]] = (row[1], row[2])
            if set(recorded) != set(files):
                raise ReadinessError(f"Incomplete wheel RECORD: {name}")
            for member, info in files.items():
                hash_text, size_text = recorded[member]
                if member == record_path:
                    if hash_text or size_text:
                        raise ReadinessError(f"Self-hashed wheel RECORD: {name}")
                    continue
                if not hash_text.startswith("sha256=") or size_text != str(info.file_size):
                    raise ReadinessError(f"Missing wheel RECORD sha256: {name}")
                with archive.open(info) as stream:
                    actual = _sha256(stream)
                if actual != hash_text.removeprefix("sha256="):
                    raise ReadinessError(f"Wheel RECORD digest mismatch: {name}")
    except (zipfile.BadZipFile, UnicodeDecodeError, OSError) as exc:
        raise ReadinessError(f"Invalid wheel archive: {name}") from exc


def wheelhouse_audit(path: Path) -> int:
    safe_wheelhouse(path)
    pins = lock.all_pins()
    # Reuse the Release 705 exact 44-package SHA inventory contract,
    # then additionally validate actual ZIP/metadata, RECORD and ABI tags.
    rows = lock.inventory(path, pins)
    tags = set(sys_tags())
    for row in rows:
        audit_wheel(path / row["filename"], pins, tags)
    print(f"DEPENDENCY_705_WHEELHOUSE_WHEELS={len(rows)}")
    print("DEPENDENCY_705_WHEELHOUSE=VALIDATED_READ_ONLY")
    print("DEPENDENCY_705_WHEEL_PROVENANCE=UNAPPROVED")
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path,
                        help="Optional preexisting private /tmp wheelhouse; never downloaded")
    args = parser.parse_args(argv)
    try:
        drift, pip_ok = runtime_audit()
        if args.wheelhouse is None:
            print("DEPENDENCY_705_WHEELHOUSE=NOT_SUPPLIED")
            print("DEPENDENCY_705_REPLAY=NOT_EXECUTED")
            print("DEPENDENCY_705_ISSUE10=BLOCKED")
            return 2 if drift or not pip_ok else 0
        wheelhouse_audit(args.wheelhouse)
        print("DEPENDENCY_705_REPLAY=NOT_EXECUTED")
        print("DEPENDENCY_705_ISSUE10=BLOCKED_PENDING_PROVENANCE_AND_REPLAY")
        return 2 if drift or not pip_ok else 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"DEPENDENCY_705_READINESS=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
