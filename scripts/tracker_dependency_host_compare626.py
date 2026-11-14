#!/usr/bin/env python3
"""Compare sanitized DEV/PROD dependency snapshots against observed pins.

Read-only. Does not install, upgrade, contact registries or inspect secrets.
Inputs are explicit user-captured JSON package inventories (pip list --format=json).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.tracker_dependency_baseline569 import (
    BASELINE, CONSTRAINTS, BaselineError, normalize_versions,
    read_manifest, read_constraints, validate_constraints,
)


def read_snapshot(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Only pip list --format=json is accepted. Never process pip config,
    # environment variables, installation paths or URL credentials.
    if not isinstance(data, list):
        raise BaselineError("Expected pip list --format=json array")
    versions = {}
    for item in data:
        if not isinstance(item, dict) or set(item) != {"name", "version"}:
            raise BaselineError("Snapshot must contain only package names and versions")
        name, version = item["name"], item["version"]
        if not isinstance(name, str) or not isinstance(version, str):
            raise BaselineError("Invalid package entry")
        if name in versions:
            raise BaselineError("Duplicate package name")
        versions[name] = version
    if not versions:
        raise BaselineError("Empty installed-package list")
    return normalize_versions(versions)


def diff(reference: dict[str, str], actual: dict[str, str]) -> list[dict]:
    rows = []
    for name in sorted(reference.keys() | actual.keys()):
        expected, observed = reference.get(name), actual.get(name)
        if expected != observed:
            rows.append({
                "package": name,
                "expected": expected,
                "actual": observed,
            })
    return rows


def compare_snapshots(dev: dict, prod: dict, baseline: dict) -> dict:
    return {
        "schema_version": 1,
        "host_comparison_only": True,
        "fresh_environment_reproduced": False,
        "baseline_packages": len(baseline),
        "dev_packages": len(dev),
        "prod_packages": len(prod),
        "dev_vs_prod": diff(dev, prod),
        "dev_vs_observed_baseline": diff(baseline, dev),
        "prod_vs_observed_baseline": diff(baseline, prod),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--prod", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--constraints", type=Path, default=CONSTRAINTS)
    args = parser.parse_args(argv)
    try:
        baseline = read_manifest(args.baseline)
        validate_constraints(baseline, read_constraints(args.constraints))
        dev, prod = read_snapshot(args.dev), read_snapshot(args.prod)
        output = compare_snapshots(dev, prod, baseline["packages"])
    except (OSError, UnicodeError, ValueError) as exc:
        # Never echo input paths or content that could contain credentials.
        print(f"DEPENDENCY_EVIDENCE=ERROR ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    if any(output[key] for key in (
        "dev_vs_prod", "dev_vs_observed_baseline", "prod_vs_observed_baseline"
    )):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
