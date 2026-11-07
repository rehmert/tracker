"""Release 432: bounded, read-only recent records for staged secondary users.

One allowlisted request per subprocess; no HTTP server, sessions, or writes.
The user identity is inherited from the parent-verified worker environment.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from .worker_probe428 import validate_environment
from .worker_read429 import private_overview429

ACTIONS = frozenset(("vitals", "doses"))
LIMIT = 10
MAX_REQUEST = 256

FIELDS = {
    "vitals": frozenset((
        "at", "weight_kg", "systolic", "diastolic", "pulse_bpm", "context",
    )),
    "doses": frozenset((
        "at", "compound", "amount", "unit", "kind", "site",
    )),
}


def parse_request432(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("Invalid private worker request length")

    def unique_fields(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate private worker request field")
            obj[key] = value
        return obj

    try:
        message = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique_fields,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private worker request") from exc

    if (
        type(message) is not dict
        or set(message) != {"action"}
        or type(message["action"]) is not str
        or message["action"] not in ACTIONS
    ):
        raise ValueError("Unsupported private worker request")

    return message["action"]


def private_recent432(user_id, private, kind):
    if kind not in ACTIONS:
        raise ValueError("Unsupported recent-record type")

    # Reuse the existing independently verified worker/storage boundary.
    private_overview429(user_id, private)

    database = private / "tracker.db"
    uri = "file:" + quote(str(database), safe="/") + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

        identity = conn.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()

        if [tuple(row) for row in identity] != [(user_id, "inactive", 426)]:
            raise RuntimeError("Private workspace identity changed")

        if kind == "vitals":
            results = conn.execute("""
                SELECT measured_at AS at, weight_kg, systolic,
                       diastolic, pulse_bpm,
                       substr(context,1,80) AS context
                FROM vital_readings
                ORDER BY measured_at DESC, id DESC
                LIMIT 10
            """).fetchall()
        else:
            results = conn.execute("""
                SELECT d.taken_at AS at, substr(c.name,1,120) AS compound,
                       d.entered_value AS amount, d.entered_unit AS unit,
                       d.kind AS kind, substr(d.site,1,80) AS site
                FROM dose_logs AS d
                JOIN vials AS v ON v.id=d.vial_id
                JOIN compounds AS c ON c.id=v.compound_id
                ORDER BY d.taken_at DESC,d.id DESC
                LIMIT 10
            """).fetchall()

    return {
        "mode": "offline-recent432",
        "user_id": user_id,
        "kind": kind,
        "items": [dict(row) for row in results],
        "login_enabled": False,
        "http_listener_started": False,
    }


def read_recent432(user_id, kind, data_root=None):
    """Parent-side API: validate the account, then invoke its isolated reader."""
    if type(kind) is not str or kind not in ACTIONS:
        raise ValueError("Unsupported recent-record type")

    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_recent432"],
        input=json.dumps({"action": kind}, separators=(",", ":")),
        cwd=SOURCE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Private record reader failed (exit "
            + str(result.returncode) + "): " + result.stderr[-1200:]
        )

    try:
        report = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid recent-record response") from exc

    if (
        type(report) is not dict
        or report.get("mode") != "offline-recent432"
        or report.get("user_id") != uid
        or report.get("kind") != kind
        or report.get("login_enabled") is not False
        or report.get("http_listener_started") is not False
    ):
        raise RuntimeError("Recent-record identity contract failed")

    items = report.get("items")
    if (
        type(items) is not list
        or len(items) > LIMIT
        or any(type(row) is not dict or set(row) != FIELDS[kind] for row in items)
    ):
        raise RuntimeError("Recent-record shape invalid")

    return report


def main():
    uid, private = validate_environment()
    action = parse_request432(sys.stdin.buffer.read(MAX_REQUEST + 1))
    print(json.dumps(private_recent432(uid, private, action), sort_keys=True))


if __name__ == "__main__":
    main()
