#!/usr/bin/env python3
"""Release 579: verify real strict-CSRF browser witness files, fail closed.

Only reads sanitized evidence emitted by the isolated Playwright tests.
Does not inspect installed data, secrets, cookies, CSRF tokens, or payloads.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

FLOWS = {
    "mobile-weight": ("/vitals", 200),
    "mobile-bp": ("/vitals", 200),
    "mobile-water": ("/food/water", 200),
    "notes-preview": ("/pages/preview", 200),
    "notes-visual-fetch": ("/pages/preview", 200),
    "native-compound": ("/compounds", 303),
}
SCHEMES = ("http", "https")
KEYS = frozenset({
    "scheme", "flow", "method", "path", "accepted_status",
    "denied_status", "signed_browser_request", "runtime_observed",
    "isolated_candidate",
})


def analyze(directory: Path) -> dict:
    # Check the original path BEFORE resolving; resolution would hide a
    # symlinked witness folder and make this test-only boundary ineffective.
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Refuse symlinked witness workspace")
    directory = directory.resolve(strict=True)
    if (directory.name != "csrf-runtime579"
            or directory.parent.parent != Path("/tmp")
            or not re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}",
                                directory.parent.name)):
        raise ValueError("Witness folder is not a disposable browser QA directory")

    expected = {
        f"{scheme}-{flow}.json" for scheme in SCHEMES for flow in FLOWS
    }
    files = {p.name for p in directory.iterdir()}
    if files != expected:
        raise ValueError("Missing or unexpected strict-browser evidence files")

    rows = []
    for scheme in SCHEMES:
        for flow, (path, status) in FLOWS.items():
            file = directory / f"{scheme}-{flow}.json"
            info = file.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError(f"Unsafe browser witness file: {file.name}")
            content = file.read_text(encoding="utf-8")
            if len(content) > 2048:
                raise ValueError("Oversized witness record")
            row = json.loads(content)
            if not isinstance(row, dict) or set(row) != KEYS:
                raise ValueError("Unexpected witness schema")
            if row != {
                "scheme": scheme, "flow": flow, "method": "POST",
                "path": path, "accepted_status": status,
                "denied_status": 403,
                "signed_browser_request": True,
                "runtime_observed": True, "isolated_candidate": True,
            }:
                raise ValueError(f"Unverified browser witness: {file.name}")
            rows.append(row)
    return {
        "status": "isolated_strict_browser_witnesses_verified",
        "observed_write_scenarios": len(rows),
        "distinct_tested_paths": sorted({row["path"] for row in rows}),
        "javascript_flows": len([r for r in rows if r["flow"].startswith("mobile") or r["flow"] == "notes-visual-fetch"]),
        "htmx_flows": len([r for r in rows if r["flow"] == "notes-preview"]),
        "native_flows": len([r for r in rows if r["flow"] == "native-compound"]),
        "limits": [
            "Witnesses cover six named browser workflows, not all JS callsites",
            "Evidence files are test-produced metadata; not a substitute for full test logs",
            "No coverage is asserted for other unsafe route declarations",
            "No installed DEV or PROD strict-CSRF policy changes",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.directory)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print("CSRF_579_STRICT_RUNTIME_EVIDENCE=VERIFIED")
    print(f"CSRF_579_OBSERVED_SCENARIOS={result['observed_write_scenarios']}")
    print("CSRF_579_TESTED_PATHS=" + ",".join(result["distinct_tested_paths"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
