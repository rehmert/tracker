#!/usr/bin/env python3
"""Release 706: exhaustive *diagnostic* signed-token reachability for the
92 unqualified CSRF routes, with a separate 155-item manual review index.

Every request executes against a disposable Tracker database in a private
/tmp directory under strict mode. A syntactically valid CSRF token reaching
a handler is NOT proof of a successful, persisted business write. Never
reduce the 92 route gaps or enable global enforcement using this report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

EXPECTED_UNMAPPED = 92
EXPECTED_MANUAL = 155
EXPECTED_SESSION = 6


class SurveyError(RuntimeError):
    pass


def private_data(path: Path) -> None:
    if (not path.is_absolute() or path.name != "data"
            or path.parent.parent != Path("/tmp")
            or not re.fullmatch(r"tracker706-csrf-probe[.][A-Za-z0-9_]{8}",
                                path.parent.name)
            or path.is_symlink() or not path.is_dir()
            or path.stat().st_mode & 0o077
            or path.parent.is_symlink() or path.parent.stat().st_mode & 0o077):
        raise SurveyError("Only a private Release 706 synthetic /tmp DB is permitted")


def make_report() -> dict:
    # The environment must be set before app/config imports.
    data = Path(os.environ.get("TRACKER_DATA_DIR", ""))
    private_data(data)
    if (os.environ.get("TRACKER_CSRF_ENFORCE") != "1"
            or os.environ.get("TRACKER_TEST_ISOLATED") != "1"
            or os.environ.get("TRACKER_INSTANCE") != "DEV"):
        raise SurveyError("Strict CSRF and isolated DEV fixture flags required")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
    from app.csrf_reporting import REPORT_HEADER
    from scripts.tracker_csrf_reconcile627 import build
    from scripts.tracker_csrf_review_queue623 import prioritized_report
    from tests.test_csrf_all_registered_negative705 import (
        registered_writes, sample_path,
    )

    historical = build()
    pending = historical["remaining_routes"]
    review = prioritized_report(Path(__file__).resolve().parents[1])
    if (len(pending) != EXPECTED_UNMAPPED
            or len(review["findings"]) != EXPECTED_MANUAL
            or historical["session_account_routes_not_certified"] != EXPECTED_SESSION):
        raise SurveyError("Frozen CSRF inventory changed; manual reassessment required")

    registered = set(registered_writes())
    rows = []
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/labs")
        token = client.cookies.get(COOKIE_NAME)
        if response.status_code != 200 or not token or not token.startswith("v1."):
            raise SurveyError("Synthetic app did not issue normal CSRF token")

        for item in pending:
            key = (item["method"], item["path"])
            path = sample_path(item["path"])
            if key not in registered:
                rows.append({
                    **item,
                    "registered": False,
                    "signed_status": None,
                    "csrf_report": None,
                    "classification": "REGISTERED_ROUTE_RECONCILIATION_REQUIRED",
                })
                continue
            # Route bodies deliberately lack business input and use nonexistent
            # numeric IDs. Any side effects occur ONLY in private synthetic DB.
            signed = client.request(
                item["method"], path,
                data={"_csrf_survey_706": "invalid-business-payload"},
                headers={HEADER_NAME: token},
                follow_redirects=False,
            )
            report = signed.headers.get(REPORT_HEADER)
            if report != "valid":
                klass = "SIGNED_TOKEN_NOT_CONFIRMED"
            elif signed.status_code >= 500:
                klass = "BUSINESS_HANDLER_ERROR_OR_UNAVAILABLE"
            elif signed.status_code == 403:
                klass = "SIGNED_BUT_HANDLER_DENIED"
            else:
                klass = "TOKEN_VALID_BUSINESS_LIFECYCLE_NOT_TESTED"
            rows.append({
                **item,
                "registered": True,
                "signed_status": signed.status_code,
                "csrf_report": report,
                "classification": klass,
            })

    totals = Counter(row["classification"] for row in rows)
    if len(rows) != EXPECTED_UNMAPPED:
        raise SurveyError("Did not classify all exact-source route gaps")
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic isolated TestClient signed-token handler reachability",
        "positive_signed_persisted_lifecycles_qualified_by_this_report": 0,
        "global_strict_csrf_authorized": False,
        "frozen_unmapped_routes": len(rows),
        "manual_review_items_still_unqualified": EXPECTED_MANUAL,
        "session_account_routes_still_unqualified": EXPECTED_SESSION,
        "counts": dict(sorted(totals.items())),
        "routes": rows,
        "priority_review_queue": review["findings"],
        "limitations": [
            "Missing/forged denial is covered separately by 705 negative matrix.",
            "A valid CSRF report header does not prove that a business write succeeded.",
            "Invalid business data may return 400/403/404/422, all requiring lifecycle review.",
            "No HTTP/HTTPS real Chromium lifecycle was performed by this report.",
            "The six session/account routes need their own enabled-session fixtures.",
            "No global strict-CSRF enforcement may be switched on using this report.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-report", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.execute_report:
        print("CSRF_706_SURVEY=NO_ACTION_REQUIRE_EXPLICIT_EXECUTE")
        return 0
    if args.output is None:
        parser.error("--output required")
    try:
        if (args.output.exists() or args.output.is_symlink()
                or not args.output.parent.is_dir()
                or args.output.parent.stat().st_mode & 0o077):
            raise SurveyError("Output evidence must be a new private path")
        result = make_report()
        with args.output.open("x", encoding="utf-8") as stream:
            os.chmod(args.output, 0o600)
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print(f"CSRF_706_ROUTING_SURVEY_ROWS={result['frozen_unmapped_routes']}")
        print(f"CSRF_706_ROUTING_SURVEY_CLASSIFICATIONS={json.dumps(result['counts'], sort_keys=True)}")
        print("CSRF_706_SIGNED_PERSISTED_WRITES_CERTIFIED=0")
        print("CSRF_706_MANUAL_REVIEW_UNCHANGED=155")
        print("CSRF_706_SESSION_ACCOUNT_UNQUALIFIED=6")
        print("CSRF_706_GLOBAL_ENFORCEMENT=BLOCKED")
        print(f"CSRF_706_EVIDENCE={args.output}")
        return 0
    except (OSError, ValueError, TypeError, KeyError, SurveyError) as exc:
        print(f"CSRF_706_SURVEY=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
