#!/usr/bin/env python3
"""Read-only comparison of a Tracker host against the observed 2026-11-11 baseline.

No installs, upgrades, writes, network calls, or changes to Tracker services.
Exit 0: exact package/runtime match and pip check pass.
Exit 2: baseline drift or broken installed dependencies.
Exit 1: invalid baseline, unreadable inventory, or command failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs/dependencies/observed-2026-11-11-py313.json"
CONSTRAINTS = ROOT / "docs/dependencies/candidate-constraints-py313.txt"
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)\Z")


class BaselineError(ValueError):
    pass


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def normalize_versions(packages: dict[str, str]) -> dict[str, str]:
    normalized = {}
    for name, version in packages.items():
        if not isinstance(name, str) or not isinstance(version, str):
            raise BaselineError("Package names and versions must be strings")
        key = canonical(name)
        if not PIN.fullmatch(f"{key}=={version}"):
            raise BaselineError("Invalid package pin")
        if key in normalized:
            raise BaselineError("Duplicate normalized package name")
        normalized[key] = version
    return normalized


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise BaselineError("Invalid dependency manifest schema")
    if not isinstance(data.get("package_versions"), dict):
        raise BaselineError("Baseline package list is missing")
    for field in ("python_version", "sqlite_version"):
        value = data.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", value):
            raise BaselineError(f"Invalid {field} baseline")
    packages = normalize_versions(data["package_versions"])
    if not packages or packages.get("pip") is None:
        raise BaselineError("Expected a complete inventory including pip")
    return {
        "python": data["python_version"],
        "sqlite": data["sqlite_version"],
        "packages": packages,
    }


def read_constraints(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PIN.fullmatch(stripped)
        if match is None:
            raise BaselineError("Constraint is not an exact version pin")
        key = canonical(match.group(1))
        if key in pins:
            raise BaselineError("Duplicate normalized constraints")
        pins[key] = match.group(2)
    return pins


def validate_constraints(baseline: dict, constraints: dict[str, str]) -> None:
    expected = {
        name: value for name, value in baseline["packages"].items()
        if name != "pip"
    }
    if constraints != expected:
        raise BaselineError("Candidate constraints disagree with observed manifest")


def pip_packages() -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True, text=True, check=True,
    )
    items = json.loads(result.stdout)
    if not isinstance(items, list):
        raise BaselineError("Invalid pip list JSON structure")
    versions = {}
    for item in items:
        if not isinstance(item, dict):
            raise BaselineError("Invalid pip list entry")
        name, version = item.get("name"), item.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise BaselineError("Missing pip list package metadata")
        if name in versions:
            raise BaselineError("Duplicate pip list package")
        versions[name] = version
    return normalize_versions(versions)


def compare(baseline: dict, actual: dict, python: str, sqlite: str) -> list[str]:
    findings = []
    if python != baseline["python"]:
        findings.append(f"PYTHON expected={baseline['python']} actual={python}")
    if sqlite != baseline["sqlite"]:
        findings.append(f"SQLITE expected={baseline['sqlite']} actual={sqlite}")
    expected = baseline["packages"]
    for name in sorted(expected.keys() | actual.keys()):
        before, after = expected.get(name), actual.get(name)
        if before != after:
            findings.append(
                f"PACKAGE {name} expected={before or 'MISSING'} "
                f"actual={after or 'MISSING'}"
            )
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", choices=("DEV", "PROD"), required=True)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--constraints", type=Path, default=CONSTRAINTS)
    args = parser.parse_args(argv)

    try:
        baseline = read_manifest(args.baseline)
        pins = read_constraints(args.constraints)
        validate_constraints(baseline, pins)
        actual = pip_packages()
        findings = compare(
            baseline, actual, platform.python_version(), sqlite3.sqlite_version
        )
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"BASELINE_AUDIT=ERROR ({type(exc).__name__})", file=sys.stderr)
        return 1

    print(f"INSTANCE={args.instance}")
    print(f"BASELINE_PACKAGES={len(baseline['packages'])}")
    print(f"INSTALLED_PACKAGES={len(actual)}")
    print(f"CANDIDATE_CONSTRAINT_PINS={len(pins)}")
    for finding in findings:
        print(f"DRIFT: {finding}")
    print(f"DRIFT_COUNT={len(findings)}")
    print(f"PIP_CHECK={'PASS' if pip_result.returncode == 0 else 'FAIL'}")
    if findings or pip_result.returncode:
        print("BASELINE_AUDIT=DRIFT")
        return 2
    print("BASELINE_AUDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
