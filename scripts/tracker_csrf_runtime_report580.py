#!/usr/bin/env python3
"""Release 580: fail closed on incomplete private strict-browser evidence.

Receipts contain only whitelisted route-pattern metadata, never cookies,
identifiers, user values, secrets, or CSRF tokens. All positive and negative
requests must have already passed actual Playwright assertions.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

EXPECTED = {
    "compound-lifecycle": (
        ("POST", "/compounds", 303),
        ("POST", "/compounds/{id}/edit", 303),
        ("POST", "/compounds/{id}/delete", 303),
    ),
    "vitals-lifecycle": (
        ("POST", "/vitals", 303),
        ("POST", "/vitals/{id}/edit", 303),
        ("DELETE", "/vitals/{id}", 200),
    ),
    "notes-lifecycle": (
        ("POST", "/pages", 303),
        ("POST", "/pages/{id}", 303),
        ("POST", "/pages/{id}/sources", 303),
        ("POST", "/sources/{id}/delete", 303),
        ("POST", "/pages/{id}/delete", 303),
    ),
}
SCHEMES = ("http", "https")
REQUIRED = {
    f"{scheme}-{flow}.json" for scheme in SCHEMES for flow in EXPECTED
}


def analyze(directory: Path) -> dict:
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Symlinked strict-browser evidence workspace")
    directory = directory.resolve(strict=True)
    if (directory.name != "csrf-runtime580"
            or directory.parent.parent != Path("/tmp")
            or not re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}",
                                directory.parent.name)):
        raise ValueError("Runtime witness path is not disposable QA")
    if {p.name for p in directory.iterdir()} != REQUIRED:
        raise ValueError("Missing or unexpected runtime witness files")
    for scheme in SCHEMES:
        for flow, operations in EXPECTED.items():
            file = directory / f"{scheme}-{flow}.json"
            mode = file.lstat().st_mode
            if not stat.S_ISREG(mode) or mode & 0o077:
                raise ValueError("Insecure runtime witness file")
            content = file.read_text(encoding="utf-8")
            if len(content) > 4096:
                raise ValueError("Oversized runtime evidence")
            record = json.loads(content)
            expected = {
                "scheme": scheme,
                "flow": flow,
                "operations": [
                    {"method": method, "route_pattern": path,
                     "signed_status": status, "unsigned_status": 403}
                    for method, path, status in operations
                ],
                "isolated_strict_browser": True,
                "real_user_interactions": True,
            }
            if type(record) is not dict or record != expected:
                raise ValueError(f"Invalid or unverified evidence: {file.name}")
    return {
        "scenarios": len(REQUIRED),
        "verified_write_operations": sum(map(len, EXPECTED.values())) * len(SCHEMES),
        "route_patterns": sorted({path for ops in EXPECTED.values()
                                 for _, path, _ in ops}),
        "disposition": "selected_flows_only_not_all_routes",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        info = analyze(args.directory)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print("CSRF_580_LIFECYCLE_EVIDENCE=VERIFIED")
    print(f"CSRF_580_LIFECYCLE_SCENARIOS={info['scenarios']}")
    print(f"CSRF_580_WRITE_OPERATIONS={info['verified_write_operations']}")
    print(f"CSRF_580_ROUTE_PATTERNS={len(info['route_patterns'])}")
    print("CSRF_580_SCOPE=SELECTED_FLOWS_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
