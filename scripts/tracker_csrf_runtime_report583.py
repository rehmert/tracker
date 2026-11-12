#!/usr/bin/env python3
"""Release 583 exact closed-schema strict-CSRF preparation lifecycle receipts."""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

SCHEMES = ("http", "https")
OPERATIONS = (
    ("POST", "/vials/{id}/reconstitute", 303),
    ("POST", "/vials/{id}/filter", 303),
    ("POST", "/vials/{id}/preparations/{event}/edit", 303),
    ("POST", "/vials/{id}/preparations/{event}/delete", 303),
)
EXPECTED = {f"{scheme}-preparation-lifecycle.json" for scheme in SCHEMES}


def analyze(folder: Path):
    if folder.is_symlink() or folder.parent.is_symlink():
        raise ValueError("Symlinked evidence directory is forbidden")
    folder = folder.resolve(strict=True)
    if not (
        folder.name == "csrf-runtime583"
        and folder.parent.parent == Path("/tmp")
        and re.fullmatch(
            r"tracker-browser-qa\.[A-Za-z0-9_]{8}", folder.parent.name
        )
    ):
        raise ValueError("Evidence requires disposable QA directory")
    if folder.stat().st_mode & 0o077:
        raise ValueError("Evidence directory is not private")
    if {p.name for p in folder.iterdir()} != EXPECTED:
        raise ValueError("Missing or extra evidence files")
    for scheme in SCHEMES:
        path = folder / f"{scheme}-preparation-lifecycle.json"
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise ValueError("Non-private evidence or symlink")
        if path.stat().st_size > 2048:
            raise ValueError("Oversized evidence")
        actual = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "scheme": scheme, "flow": "preparation-lifecycle",
            "operations": [
                {"method": method, "route_pattern": route,
                 "signed_status": status, "unsigned_status": 403}
                for method, route, status in OPERATIONS
            ],
            "strict_candidate": True, "synthetic_qa_data_only": True,
            "signed_lifecycle_verified": True,
            "inventory_verified_separately": True,
        }
        if type(actual) is not dict or actual != expected:
            raise ValueError(f"Invalid evidence: {path.name}")
    return {"browser_cases": 2, "signed_writes": 8, "forgery_rejections": 8}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.directory)
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print("CSRF_583_PREPARATION_EVIDENCE=VERIFIED")
    print(f"CSRF_583_SIGNED_WRITES={result['signed_writes']}")
    print(f"CSRF_583_FORGERY_REJECTIONS={result['forgery_rejections']}")
    print("CSRF_583_SCOPE=VIAL_PREPARATION_HTTP_HTTPS_ONLY")


if __name__ == "__main__":
    main()
