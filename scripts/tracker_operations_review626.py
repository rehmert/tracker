#!/usr/bin/env python3
"""Offline operations review summary. Never queries live services or databases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.tracker_csrf_review_queue623 import prioritized_report
from scripts.tracker_dependency_baseline569 import BASELINE, CONSTRAINTS, read_manifest, read_constraints, validate_constraints
from scripts.tracker_release_diagnostics626 import summarize as summarize_release


def dashboard(root: Path, transcript: str | None = None) -> dict:
    csrf = prioritized_report(root)
    manifest_path = root / "docs/dependencies/observed-2026-11-11-py313.json"
    pins_path = root / "docs/dependencies/candidate-constraints-py313.txt"
    manifest = read_manifest(manifest_path)
    pins = read_constraints(pins_path)
    validate_constraints(manifest, pins)
    result = {
        "schema_version": 1,
        "read_only": True,
        "live_host_status": "NOT_CHECKED",
        "csrf": {
            "runtime_verified": False,
            "findings_by_review_priority": csrf["totals"]["by_priority"],
            "review_items": csrf["totals"]["review_items"],
            "strict_enforcement_qualified": False,
        },
        "dependencies": {
            "historical_observed_packages": len(manifest["packages"]),
            "candidate_constraint_pins": len(pins),
            "fresh_environment_reproduced": False,
            "dev_prod_current_versions_checked": False,
        },
        "release": (summarize_release(transcript) if transcript is not None
                    else {"evidence": "NOT_PROVIDED"}),
        "notes": [
            "This is an offline source and optional supplied-log review, not an authenticated in-app console.",
            "Priority labels are not severity, and passing static audits does not establish effective CSRF.",
            "Installed packages, service health and signed deployment state are not checked.",
        ],
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--release-log", type=Path)
    args = parser.parse_args(argv)
    try:
        log = args.release_log.read_text(encoding="utf-8", errors="replace") if args.release_log else None
        result = dashboard(args.root.resolve(), log)
    except (OSError, ValueError, UnicodeError):
        parser.error("Invalid offline review evidence")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
