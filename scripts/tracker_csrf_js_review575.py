#!/usr/bin/env python3
"""Release 575: source-only review queue for JS fetch and HTMX callsites.

A nearby method literal is only a triage hint, NEVER proof of which
HTTP method executes at runtime or whether CSRF is present. The report
never includes credentials or request values, only tracked source lines.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "scripts/tracker-csrf-readiness.py"
_METHOD = re.compile(r"""\bmethod\s*:\s*['"](?P<method>GET|POST|PUT|PATCH|DELETE)['"]""", re.I)
_DYNAMIC = re.compile(r"\bmethod\s*:")
_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def source_inventory(root: Path = ROOT) -> dict:
    spec = importlib.util.spec_from_file_location(
        "tracker_csrf_js_review575_static", root / "scripts/tracker-csrf-readiness.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the tracked CSRF source scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(root)


def classify_callsite(record: dict, root: Path = ROOT) -> dict:
    path = root / record["file"]
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("JS callsite escaped repository") from exc
    if not path.is_file():
        raise ValueError("JS callsite source missing")
    lines = path.read_text(encoding="utf-8").splitlines()
    number = record["line"]
    if not isinstance(number, int) or not 1 <= number <= len(lines):
        raise ValueError("JS callsite line is invalid")

    # We intentionally inspect only a short window around each callsite
    # and retain an explicit unknown category for all indirect options.
    nearby = "\n".join(lines[number - 1:min(len(lines), number + 9)])
    matches = _METHOD.findall(nearby)
    method_names = sorted(set(x.upper() for x in matches))
    if record["kind"] == "htmx_ajax_callsite":
        classification = "htmx_programmatic_manual_review"
    elif any(x in _UNSAFE for x in method_names):
        classification = "unsafe_method_literal_nearby"
    elif _DYNAMIC.search(nearby):
        classification = "dynamic_method_manual_review"
    else:
        classification = "no_unsafe_literal_nearby_manual_review"
    return {
        **record,
        "classification": classification,
        "nearby_literal_methods": method_names,
        # Excerpt is exclusively from tracked source and excludes data.
        "source_line": lines[number - 1].strip()[:220],
    }


def build(root: Path = ROOT) -> dict:
    scanned = source_inventory(root)
    rows = [classify_callsite(item, root)
            for item in scanned["javascript"]]
    groups = Counter(row["classification"] for row in rows)
    return {
        "status": "source_triage_only_not_security_clearance",
        "summary": {
            "js_request_callsites": len(rows),
            "classes": dict(sorted(groups.items())),
            "unreviewed_runtime_effects": len(rows),
        },
        "limitations": [
            "Nearby method literals do not prove the method actually used",
            "A GET-looking or unknown callsite may still perform unsafe writes",
            "Every JavaScript write remains subject to real-browser acceptance tests",
            "No installed Tracker security configuration changes",
        ],
        "callsites": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = build()
    print("CSRF_JS_REVIEW=READ_ONLY")
    for k, v in report["summary"].items():
        print(f"{k.upper()}={v}")
    for row in report["callsites"]:
        print(f"{row['classification']} {row['file']}:{row['line']}")
    print("JS_RUNTIME_COMPATIBILITY=MANUAL_REVIEW_REQUIRED")
    if args.json is not None:
        dest = args.json
        if (dest.parent.parent != Path("/tmp")
                or not dest.parent.name.startswith("tracker-csrf575.")
                or not dest.parent.is_dir()
                or dest.parent.is_symlink()
                or dest.exists() or dest.is_symlink()):
            parser.error("--json must be a fresh file in /tmp/tracker-csrf575.*/")
        with dest.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        dest.chmod(0o600)
        print(f"JS_REVIEW_JSON={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
