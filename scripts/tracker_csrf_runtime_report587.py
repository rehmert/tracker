#!/usr/bin/env python3
"""Fail-closed verifier for isolated Release 587 bulk-vial browser evidence.

The presence of receipts certifies only the specific synthetic browser-fetch
operations enumerated here, not native form, account, or global CSRF readiness.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
from pathlib import Path

ROUTES = (
    ("/vials/bulk/validate-selection", 200),
    ("/vials/bulk/preview", 200),
    ("/vials/bulk", 303),
    ("/vials/bulk/delete-preview", 200),
    ("/vials/bulk/delete", 303),
)


def verify(folder: Path) -> None:
    folder = folder.resolve(strict=True)
    if not (
        folder.name == "csrf-runtime587"
        and folder.parent.parent == Path("/tmp")
        and re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}", folder.parent.name)
        and folder.parent.is_dir()
    ):
        raise ValueError("Unexpected isolated QA directory")
    names = {"http-bulk.json", "https-bulk.json"}
    found = {entry.name for entry in folder.iterdir()}
    if found != names:
        raise ValueError(f"Expected exact two receipts; found: {sorted(found)}")
    for name in sorted(names):
        path = folder / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError(f"Insecure receipt: {name}")
        if info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError(f"Unexpected receipt ownership/link count: {name}")
        if info.st_size > 8192:
            raise ValueError("Receipt too large")
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        scheme = name.split("-", 1)[0]
        expected = {
            "scheme": scheme,
            "flow": "vial-bulk-fetch-lifecycle",
            "operations": [
                {"method": "POST", "route_pattern": route,
                 "signed_status": status, "unsigned_status": 403}
                for route, status in ROUTES
            ],
            "synthetic_qa_data_only": True,
            "signed_browser_fetch": True,
            "redirects_followed_and_success_flash_verified": True,
            "native_bulk_form_submission_tested": False,
            "csrf_enforcement_installed": False,
            "persisted_update_and_delete_verified": True,
        }
        if record != expected:
            raise ValueError(f"Unrecognized or incomplete receipt: {name}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, required=True)
    args = p.parse_args()
    try:
        verify(args.directory)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.exit(1, f"CSRF_587_BULK_EVIDENCE=FAILED: {exc}\n")
    print("CSRF_587_BULK_EVIDENCE=VERIFIED")
    print("CSRF_587_SCHEMES=HTTP_HTTPS")
    print("CSRF_587_SIGNED_BROWSER_FETCH_WRITES=10")
    print("CSRF_587_UNSIGNED_REJECTIONS=10")
    print("CSRF_587_SCOPE=BULK_VIAL_FETCH_ONLY_NOT_GLOBAL_CLEARANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
