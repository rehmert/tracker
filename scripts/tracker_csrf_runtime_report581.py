#!/usr/bin/env python3
"""Release 581: closed-schema private CSRF evidence, no overclaimed clearance."""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

NEGATIVE = {
    "vial-delete": ("POST", "/vials/{id}/delete"),
    "vial-reconstitute": ("POST", "/vials/{id}/reconstitute"),
    "vial-filter": ("POST", "/vials/{id}/filter"),
    "dose-create": ("POST", "/doses"),
    "dose-delete": ("DELETE", "/doses/{id}"),
    "dose-preview": ("POST", "/doses/preview"),
}
POSITIVE = {
    "vial-native-update": ("POST", "/vials/{id}", 303),
    "dose-htmx-preview": ("POST", "/doses/preview", 200),
}
SCHEMES = ("http", "https")
REQUIRED = {
    f"{scheme}-{name}.json"
    for scheme in SCHEMES for name in (*POSITIVE, *NEGATIVE)
}


def analyze(directory: Path) -> dict:
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Refuse symlinked browser evidence directory")
    directory = directory.resolve(strict=True)
    if (
        directory.name != "csrf-runtime581"
        or directory.parent.parent != Path("/tmp")
        or not re.fullmatch(
            r"tracker-browser-qa\.[A-Za-z0-9_]{8}", directory.parent.name
        )
    ):
        raise ValueError("Evidence must be generated in disposable /tmp browser QA")
    if {p.name for p in directory.iterdir()} != REQUIRED:
        raise ValueError("Missing or extra browser evidence files")
    for scheme in SCHEMES:
        for name in (*POSITIVE, *NEGATIVE):
            file = directory / f"{scheme}-{name}.json"
            mode = file.lstat().st_mode
            if not stat.S_ISREG(mode) or mode & 0o077:
                raise ValueError(f"Non-private browser evidence: {file.name}")
            content = file.read_text(encoding="utf-8")
            if len(content) > 2048:
                raise ValueError("Evidence too large")
            row = json.loads(content)
            if name in POSITIVE:
                method, path, expected_status = POSITIVE[name]
                kind = "positive"
            else:
                method, path = NEGATIVE[name]
                expected_status = None
                kind = "negative"
            expected = {
                "scheme": scheme, "flow": name, "kind": kind,
                "method": method, "route_pattern": path,
                "signed_status": expected_status,
                "unsigned_status": 403,
                "strict_candidate": True,
                "synthetic_qa_data_only": True,
            }
            if type(row) is not dict or row != expected:
                raise ValueError(f"Unverified or altered evidence: {file.name}")
    return {
        "browser_cases": len(REQUIRED),
        "signed_positive_cases": len(POSITIVE) * len(SCHEMES),
        "negative_only_cases": len(NEGATIVE) * len(SCHEMES),
        "signed_write_route_patterns": sorted({v[1] for v in POSITIVE.values()}),
        "negative_only_route_patterns": sorted({v[1] for v in NEGATIVE.values()}),
        "limits": [
            "Negative-only routes have NOT proven signed write compatibility",
            "No secondary-account isolation is claimed by these browser scenarios",
            "Existing JS callsite inventory remains separate and open",
            "No installed strict-CSRF policy change",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        info = analyze(args.directory)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print("CSRF_581_INVENTORY_DOSE_EVIDENCE=VERIFIED")
    print(f"CSRF_581_BROWSER_CASES={info['browser_cases']}")
    print(f"CSRF_581_SIGNED_POSITIVE_CASES={info['signed_positive_cases']}")
    print(f"CSRF_581_NEGATIVE_ONLY_CASES={info['negative_only_cases']}")
    print("CSRF_581_SCOPE=SELECTED_ROUTES_NOT_ALL_JS_CALLSITES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
