#!/usr/bin/env python3
"""Release 576: conservative source-to-route JS CSRF triage, not clearance.

Read-only: never imports the running application, contacts a server, reads
secrets, or changes installed CSRF policy. Evidence is deliberately marked
non-executable until a disposable browser scenario establishes behavior.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/tracker_csrf_js_review575.py"
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
METHOD = re.compile(r"""\bmethod\s*:\s*['"](?P<method>GET|POST|PUT|PATCH|DELETE)['"]""", re.I)
URL = re.compile(r"""\bfetch\s*\(\s*['"](?P<url>/[^'"\s]*)['"]""")
HTMX = re.compile(r"""\bhtmx\.ajax\s*\(\s*['"](?P<method>GET|POST|PUT|PATCH|DELETE)['"]\s*,\s*['"](?P<url>/[^'"\s]*)['"]""", re.I)


def load_baseline(root: Path):
    spec = importlib.util.spec_from_file_location("csrf575_for576", root / "scripts/tracker_csrf_js_review575.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing Release 575 inventory")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(root)


def inspect(row: dict, root: Path) -> dict:
    path = (root / row["file"]).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Source path escaped repository") from exc
    lines = path.read_text(encoding="utf-8").splitlines()
    n = row["line"]
    if not isinstance(n, int) or not 1 <= n <= len(lines):
        raise ValueError("Invalid source line")
    # Only use line-local literal evidence as a confident syntactic hint.
    # Never attach a nearby method belonging to a DIFFERENT fetch call.
    current = lines[n - 1]
    window = "\n".join(lines[n - 1:min(n + 7, len(lines))])
    htmx = HTMX.search(window) if row["kind"] == "htmx_ajax_callsite" else None
    url = URL.search(current) if row["kind"] == "fetch_callsite" else None
    # A method on the callsite line is still source-only, not runtime proof.
    literal_method = (htmx.group("method").upper() if htmx else
                      METHOD.search(current).group("method").upper() if METHOD.search(current)
                      else None)
    literal_path = htmx.group("url") if htmx else url.group("url") if url else None
    hints = sorted(set(m.upper() for m in METHOD.findall(window)))
    if literal_method in UNSAFE:
        triage = "explicit_unsafe_method_on_callsite_line"
    elif literal_method == "GET":
        triage = "explicit_get_on_callsite_line"
    elif any(m in UNSAFE for m in hints):
        triage = "nearby_unsafe_hint_unresolved"
    elif hints:
        triage = "nearby_get_hint_unresolved"
    else:
        triage = "method_unknown"
    return {
        "file": row["file"], "line": n, "kind": row["kind"],
        "baseline_classification": row["classification"],
        "triage": triage, "callsite_line_method": literal_method,
        "callsite_line_path": literal_path,
        "nearby_methods_untrusted": hints,
        "browser_verified": False,
    }


def build(root: Path = ROOT) -> dict:
    baseline = load_baseline(root)
    rows = [inspect(row, root) for row in baseline["callsites"]]
    if len(rows) != baseline["summary"]["js_request_callsites"]:
        raise ValueError("Inventory count changed during inspection")
    keys = [(r["file"], r["line"], r["kind"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate JS source callsites")
    counts = Counter(r["triage"] for r in rows)
    return {
        "status": "source_only_no_strict_csrf_clearance",
        "summary": {
            "javascript_callsites": len(rows),
            "browser_verified": 0,
            "pending_executable_review": len(rows),
            "triage": dict(sorted(counts.items())),
        },
        "limits": [
            "Method and path on the same source line remain syntactic hints, not runtime behavior",
            "Nearby method hints may belong to other requests or branches",
            "Dynamic routes, template substitutions, and wrapped fetch options require manual review",
            "No per-route compatibility claim and no installed strict-CSRF policy changes",
        ],
        "callsites": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = build()
    print("CSRF_576_SOURCE_TRIAGE=READ_ONLY_NOT_CLEARANCE")
    for key, value in report["summary"].items():
        print(f"{key.upper()}={value}")
    for row in report["callsites"]:
        print(f"{row['triage']} {row['file']}:{row['line']} method={row['callsite_line_method'] or '?'} path={row['callsite_line_path'] or '?'}")
    if args.json:
        dest = args.json
        if (dest.parent.parent != Path("/tmp")
                or not dest.parent.name.startswith("tracker-csrf576.")
                or not dest.parent.is_dir() or dest.parent.is_symlink()
                or dest.exists() or dest.is_symlink()):
            parser.error("--json requires fresh /tmp/tracker-csrf576.*/ destination")
        with dest.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        dest.chmod(0o600)
        print(f"REPORT={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
