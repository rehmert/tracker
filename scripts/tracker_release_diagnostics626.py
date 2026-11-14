#!/usr/bin/env python3
"""Read-only, sanitized classification of a Tracker release transcript.

Never emits raw log lines, addresses, exception text, tokens or paths. This
cannot determine why an SSH client disconnected, or establish host health.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

COMMIT = re.compile(r"^[0-9a-f]{40}$")
KEYS = ("EXIT_STATUS", "DEV_QUALIFICATION_EVIDENCE_PRESERVED",
        "PROD_DEPLOY_VERIFIED", "REMOTE_DEPLOY_EXIT_STATUS",
        "PROD_INSTALLED_COMMIT", "DEV_CONTROLLED_RELEASE")
MATCH = re.compile(r"^(?:" + "|".join(KEYS) + r")=")


def summarize(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        if MATCH.match(line):
            key, value = line.split("=", 1)
            if key in ("PROD_DEPLOY_VERIFIED", "PROD_INSTALLED_COMMIT"):
                values[key] = value if COMMIT.fullmatch(value) else "INVALID"
            elif key in ("EXIT_STATUS", "REMOTE_DEPLOY_EXIT_STATUS"):
                values[key] = value if value.isdecimal() else "INVALID"
            elif key == "DEV_CONTROLLED_RELEASE":
                values[key] = value if value in ("SUCCESS", "FAILED") else "UNKNOWN"
            else:
                # This key normally contains a host path. Never print it.
                values[key] = "PRESENT" if value else "MISSING"
    success_marker = "TRACKER RELEASE DEPLOYMENT SUCCESS" in text
    prod_complete = (
        values.get("REMOTE_DEPLOY_EXIT_STATUS") == "0"
        and values.get("DEV_CONTROLLED_RELEASE") == "SUCCESS"
        and values.get("PROD_DEPLOY_VERIFIED") == values.get("PROD_INSTALLED_COMMIT")
        and bool(COMMIT.fullmatch(values.get("PROD_INSTALLED_COMMIT", "")))
    )
    dev_complete = (
        values.get("EXIT_STATUS") == "0"
        and values.get("DEV_QUALIFICATION_EVIDENCE_PRESERVED") == "PRESENT"
    )
    return {
        "schema_version": 1,
        "sanitized": True,
        "success_banner_observed": success_marker,
        "dev_receipt_markers_complete": dev_complete,
        "prod_promotion_markers_complete": prod_complete,
        "markers": values,
        "ssh_disconnect_cause": "NOT_DETERMINABLE_FROM_RELEASE_LOG",
        "notes": [
            "Markers document reported outcomes; this does not independently attest host state.",
            "For disconnections, correlate systemd journal, sshd logs, kernel OOM and host uptime using separate privileged observation.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        data = args.log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        parser.error("Cannot read release transcript")
    print(json.dumps(summarize(data), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
