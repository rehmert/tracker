#!/usr/bin/env python3
"""Release 582: fail-closed receipt for signed dose CRUD on isolated QA."""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

OPERATIONS = (
    ("POST", "/doses", 200),
    ("POST", "/doses/{id}/edit", 303),
    ("DELETE", "/doses/{id}", 200),
)
SCHEMES = ("http", "https")
EXPECTED_FILES = {f"{scheme}-dose-lifecycle.json" for scheme in SCHEMES}


def analyze(directory: Path) -> dict:
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Symlinked evidence directory not permitted")
    directory = directory.resolve(strict=True)
    if (
        directory.name != "csrf-runtime582"
        or directory.parent.parent != Path("/tmp")
        or not re.fullmatch(
            r"tracker-browser-qa\.[A-Za-z0-9_]{8}", directory.parent.name
        )
    ):
        raise ValueError("Evidence must reside in disposable browser QA")
    if directory.stat().st_mode & 0o077:
        raise ValueError("Evidence directory must be private")
    if {entry.name for entry in directory.iterdir()} != EXPECTED_FILES:
        raise ValueError("Missing or extra browser evidence")
    for scheme in SCHEMES:
        path = directory / f"{scheme}-dose-lifecycle.json"
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise ValueError("Evidence is not a private regular file")
        if path.stat().st_size > 2048:
            raise ValueError("Evidence file too large")
        actual = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "scheme": scheme,
            "flow": "dose-lifecycle",
            "operations": [
                {"method": method, "route_pattern": route,
                 "signed_status": status, "unsigned_status": 403}
                for method, route, status in OPERATIONS
            ],
            "strict_candidate": True,
            "synthetic_qa_data_only": True,
            "signed_lifecycle_verified": True,
        }
        if type(actual) is not dict or actual != expected:
            raise ValueError(f"Invalid or altered browser evidence: {path.name}")
    return {
        "protocols": len(SCHEMES),
        "signed_writes": len(SCHEMES) * len(OPERATIONS),
        "forgery_rejections": len(SCHEMES) * len(OPERATIONS),
        "verified_route_patterns": [route for _, route, _ in OPERATIONS],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.directory)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print("CSRF_582_DOSE_LIFECYCLE_EVIDENCE=VERIFIED")
    print(f"CSRF_582_SIGNED_WRITES={result['signed_writes']}")
    print(f"CSRF_582_FORGERY_REJECTIONS={result['forgery_rejections']}")
    print("CSRF_582_SCOPE=DOSE_CRUD_HTTP_HTTPS_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
