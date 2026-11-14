#!/usr/bin/env python3
"""Conservative, read-only inventory of potential JavaScript HTTP writes.

This is a source-text review aid, not JavaScript parsing or CSRF validation.
It intentionally reports uncertain call sites and never executes JavaScript.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
# Literal methods only. Dynamic method expressions are not proved safe.
METHOD = r"""['"](?:POST|PUT|PATCH|DELETE)['"]"""
FETCH = re.compile(r"\bfetch\s*\(", re.I)
XHR = re.compile(r"\.open\s*\(\s*(" + METHOD + r")\s*,", re.I)
HTMX = re.compile(r"\bhtmx\.ajax\s*\(\s*(" + METHOD + r")\s*,", re.I)
METHOD_FIELD = re.compile(r"""\bmethod\s*:\s*(""" + METHOD + r")", re.I)
MAX_WINDOW = 500


def candidates(text: str) -> list[dict]:
    rows = []
    for line_num, line in enumerate(text.splitlines(), 1):
        # A candidate is not considered a verified write. Multi-line method
        # configuration is captured only as a nearby hint, never as proof.
        for kind, rx in (("fetch", FETCH), ("xhr-open", XHR), ("htmx-ajax", HTMX)):
            for match in rx.finditer(line):
                context = line[match.start():match.start() + MAX_WINDOW]
                method = None
                if kind == "fetch":
                    method_match = METHOD_FIELD.search(context)
                    if method_match:
                        method = method_match.group(1).strip("'\"").upper()
                else:
                    method = match.group(1).strip("'\"").upper()
                rows.append({
                    "line": line_num,
                    "kind": kind,
                    "method_hint": method or "UNKNOWN",
                    "review_status": "MANUAL_REVIEW_REQUIRED",
                })
    return rows


def inventory(root: Path) -> list[dict]:
    locations = [root / "app" / "static", root / "app" / "templates"]
    files = sorted(
        p for base in locations if base.is_dir()
        for p in base.rglob("*") if p.is_file()
        and p.suffix.lower() in ((".js", ".html") if base.name == "templates" else (".js",))
    )
    rows = []
    for path in files:
        for row in candidates(path.read_text(encoding="utf-8")):
            rows.append({"file": str(path.relative_to(root)), **row})
    return rows


def report(root: Path) -> dict:
    rows = inventory(root)
    return {
        "schema_version": 1,
        "scope": "JavaScript source-text call sites in static JS and templates",
        "runtime_csrf_verification": False,
        "total_candidate_call_sites": len(rows),
        "method_unknown_candidates": sum(r["method_hint"] == "UNKNOWN" for r in rows),
        "candidates": rows,
        "limitations": [
            "Method hints only use same-line literal expressions and can miss multiline or dynamic methods.",
            "Occurrences in comments or strings may be false positives.",
            "Calls via wrappers, event dispatch, libraries, aliases, external scripts or template-generated JavaScript may be missed.",
            "No candidate implies a vulnerable or protected route; manually inspect request construction, origins, tokens and runtime behavior.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "app").is_dir():
        parser.error("App source directory not found")
    print(json.dumps(report(root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
