"""Release 433: one allowlisted vital-reading write in a verified private worker.

This is not a general SQL API. The HTTP gateway controls authorization and
CSRF; this separate process independently verifies storage and payload data.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from .worker_probe428 import validate_environment
from .worker_read429 import private_overview429

MAX_BYTES = 4096
OPERATION = "secondary_vital_create433"
REQUIRED = frozenset({
    "measured_at", "weight_kg", "systolic", "diastolic", "pulse_bpm",
    "context", "notes", "submission_token",
})


def parse_vital433(raw):
    """Accept a small, exact-schema payload; reject paths, SQL and user IDs."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid vitals request size")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate request field")
            result[key] = value
        return result

    try:
        request = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid vitals request JSON") from exc

    if type(request) is not dict or set(request) != {"action", "payload"}:
        raise ValueError("Unexpected vitals request fields")
    if request["action"] != "create_vital" or type(request["payload"]) is not dict:
        raise ValueError("Unsupported vitals request action")

    payload = request["payload"]
    if set(payload) != REQUIRED:
        raise ValueError("Unexpected vital fields")

    timestamp = payload["measured_at"]
    if type(timestamp) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", timestamp):
        raise ValueError("Invalid measurement time")
    try:
        when = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("Invalid measurement time") from exc
    if when < datetime(2000, 1, 1) or when > datetime.now() + timedelta(days=1):
        raise ValueError("Measurement time outside supported range")

    weight = payload["weight_kg"]
    if weight is not None and (type(weight) not in (int, float) or not math.isfinite(weight)):
        raise ValueError("Invalid weight")

    for name in ("systolic", "diastolic", "pulse_bpm"):
        value = payload[name]
        if value is not None and type(value) is not int:
            raise ValueError("Invalid " + name)

    context = payload["context"]
    notes = payload["notes"]
    if (
        type(context) is not str or len(context) > 80
        or type(notes) is not str or len(notes) > 2000
        or any(ord(char) < 32 and char not in "\n\t" for char in context + notes)
    ):
        raise ValueError("Invalid context or notes")

    from . import metrics
    errors = metrics.validate(weight, payload["systolic"], payload["diastolic"], payload["pulse_bpm"])
    if errors:
        raise ValueError(" ".join(errors))

    token = payload["submission_token"]
    if type(token) is not str:
        raise ValueError("Invalid submission token")
    try:
        parsed = uuid.UUID(token)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid submission token") from exc
    if parsed.version != 4 or str(parsed) != token:
        raise ValueError("Invalid submission token")

    return payload


def form_payload433(form):
    """Convert browser form strings to the worker's strict value schema."""
    names = {
        "csrf_token", "submission_token", "measured_at", "weight",
        "weight_unit", "systolic", "diastolic", "pulse_bpm", "context", "notes",
    }
    if set(form) != names or any(len(form.getlist(name)) != 1 for name in names):
        raise ValueError("Unexpected vital form fields")

    raw = str(form["weight"]).strip()
    unit = str(form["weight_unit"]).strip()
    if unit not in ("lb", "kg"):
        raise ValueError("Invalid weight unit")

    if raw:
        if len(raw) > 12 or not re.fullmatch(r"(?:\d{1,4})(?:\.\d{1,2})?", raw):
            raise ValueError("Invalid weight")
        weight = float(raw)
        if unit == "lb":
            from .metrics import KG_PER_LB
            weight *= KG_PER_LB
    else:
        weight = None

    def optional_int(name):
        text = str(form[name]).strip()
        if not text:
            return None
        if not re.fullmatch(r"\d{1,3}", text):
            raise ValueError("Invalid " + name)
        return int(text)

    result = {
        "measured_at": str(form["measured_at"]).strip(),
        "weight_kg": weight,
        "systolic": optional_int("systolic"),
        "diastolic": optional_int("diastolic"),
        "pulse_bpm": optional_int("pulse_bpm"),
        "context": str(form["context"]).strip(),
        "notes": str(form["notes"]).strip(),
        "submission_token": str(form["submission_token"]).strip(),
    }
    parse_vital433(json.dumps({"action": "create_vital", "payload": result}).encode())
    return result


def private_create_vital433(uid, private, payload):
    """Single BEGIN IMMEDIATE transaction with durable replay rejection."""
    if os.getenv("TRACKER_WORKER_VITAL_WRITE433") != "1":
        raise PermissionError("Private vital write is disabled")

    parse_vital433(json.dumps({"action": "create_vital", "payload": payload}).encode())
    private_overview429(uid, private)
    database = private / "tracker.db"
    uri = "file:" + quote(str(database), safe="/") + "?mode=rw"
    token = payload["submission_token"]
    digest = hashlib.sha256(json.dumps(
        {key: value for key, value in payload.items() if key != "submission_token"},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()

    with sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        identity = conn.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
        if identity != [(uid, "inactive", 426)]:
            raise RuntimeError("Private workspace identity changed")

        existing = conn.execute(
            "SELECT token FROM inventory_submissions WHERE token=?", (token,),
        ).fetchone()
        if existing:
            return {"user_id": uid, "status": "duplicate", "written": False}

        cursor = conn.execute("""
            INSERT INTO vital_readings
                (measured_at,weight_kg,systolic,diastolic,pulse_bpm,context,notes)
            VALUES (?,?,?,?,?,?,?)
        """, (
            payload["measured_at"], payload["weight_kg"], payload["systolic"],
            payload["diastolic"], payload["pulse_bpm"], payload["context"],
            payload["notes"],
        ))
        conn.execute("""
            INSERT INTO inventory_submissions (token,operation,payload_hash)
            VALUES (?,?,?)
        """, (token, OPERATION, digest))
        conn.commit()
        return {"user_id": uid, "status": "created", "written": True, "id": cursor.lastrowid}


def create_vital_for_user433(uid, payload, data_root=None):
    """Parent-side caller: accept only a real staged secondary identity."""
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428
    from . import config

    if config.instance_label() != "DEV" or os.getenv("TRACKER_SECONDARY_VITAL_WRITES433") != "1":
        raise PermissionError("Secondary vitals logging is disabled")

    uid = secondary_id(uid)
    parse_vital433(json.dumps({"action": "create_vital", "payload": payload}).encode())
    env = worker_environment428(uid, data_root)
    env["TRACKER_WORKER_VITAL_WRITE433"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_vital_write433"],
        input=json.dumps({"action": "create_vital", "payload": payload}, separators=(",", ":")),
        cwd=SOURCE_ROOT, env=env,
        capture_output=True, text=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Private vital writer failed (exit " + str(result.returncode) + "): "
            + result.stderr[-1200:]
        )
    try:
        response = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid private vital response") from exc
    if (
        type(response) is not dict
        or response.get("user_id") != uid
        or response.get("status") not in ("created", "duplicate")
        or type(response.get("written")) is not bool
        or response["written"] != (response["status"] == "created")
        or (response["status"] == "created" and type(response.get("id")) is not int)
    ):
        raise RuntimeError("Private vital write identity contract failed")
    return response


def main():
    uid, private = validate_environment()
    payload = parse_vital433(sys.stdin.buffer.read(MAX_BYTES + 1))
    print(json.dumps(private_create_vital433(uid, private, payload), sort_keys=True))


if __name__ == "__main__":
    main()
