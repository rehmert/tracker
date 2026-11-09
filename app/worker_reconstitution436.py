"""Release 436: isolated, one-time reconstitution for private secondary vials.

Only the recorded liquid volume and preparation event are written. This pilot
does NOT deduct BAC water or disposable supplies, and cannot edit an existing
reconstitution. No user/database selection is accepted from browser payloads.
"""

import json
import math
import os
import re
import subprocess
import sys
import uuid
from datetime import date

from .worker_probe428 import validate_environment
from .worker_dose_write434 import _verified_storage

MAX_BYTES = 1024
OPERATION = "secondary_reconstitute436"
FIELDS = frozenset(("vial_id", "volume_ml", "submission_token"))
ACTIONS = frozenset(("options", "reconstitute"))


def _no_duplicate_fields(pairs):
    values = {}
    for key, val in pairs:
        if key in values:
            raise ValueError("Duplicate reconstitution field")
        values[key] = val
    return values


def validate_payload436(payload):
    if type(payload) is not dict or set(payload) != FIELDS:
        raise ValueError("Unexpected reconstitution fields")
    vial_id = payload["vial_id"]
    volume = payload["volume_ml"]
    token = payload["submission_token"]
    if type(vial_id) is not int or not 1 <= vial_id <= 2147483647:
        raise ValueError("Invalid vial selection")
    if (
        type(volume) not in (int, float)
        or not math.isfinite(volume)
        or not 0 < volume <= 1000
    ):
        raise ValueError("Invalid reconstitution volume")
    if type(token) is not str:
        raise ValueError("Invalid submission token")
    try:
        parsed = uuid.UUID(token)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid submission token") from exc
    if parsed.version != 4 or str(parsed) != token:
        raise ValueError("Invalid submission token")
    return {
        "vial_id": vial_id,
        "volume_ml": float(volume),
        "submission_token": token,
    }


def parse_request436(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid reconstitution request size")
    try:
        data = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_no_duplicate_fields,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid reconstitution JSON") from exc
    if type(data) is not dict or type(data.get("action")) is not str:
        raise ValueError("Invalid reconstitution request")
    action = data["action"]
    if action not in ACTIONS:
        raise ValueError("Unsupported reconstitution operation")
    if action == "options":
        if set(data) != {"action"}:
            raise ValueError("Unexpected options fields")
        return action, None
    if set(data) != {"action", "payload"}:
        raise ValueError("Unexpected write fields")
    return action, validate_payload436(data["payload"])


def form_payload436(form):
    expected = FIELDS | {"csrf_token"}
    if set(form) != expected or any(len(form.getlist(key)) != 1 for key in expected):
        raise ValueError("Unexpected or repeated form fields")
    raw_id = str(form["vial_id"]).strip()
    raw_volume = str(form["volume_ml"]).strip()
    if not re.fullmatch(r"[1-9]\d{0,9}", raw_id):
        raise ValueError("Invalid vial selection")
    if not re.fullmatch(r"\d{1,4}(?:\.\d{1,4})?", raw_volume):
        raise ValueError("Invalid volume")
    return validate_payload436({
        "vial_id": int(raw_id),
        "volume_ml": float(raw_volume),
        "submission_token": str(form["submission_token"]).strip(),
    })


def _response(uid, status, *, error="", record_id=None, options=None):
    result = {
        "mode": "private-reconstitution436",
        "user_id": uid,
        "status": status,
        "login_enabled": False,
        "http_listener_started": False,
    }
    if status == "options":
        result["options"] = options
    else:
        result["written"] = status == "created"
        if status == "rejected":
            result["error"] = error
        if record_id is not None:
            result["id"] = record_id
    return result


def private_options436(uid, private):
    from sqlalchemy import select, exists
    from .models import Vial, PreparationEvent, DoseLog

    SessionLocal = _verified_storage(uid, private)
    with SessionLocal() as session:
        marker = [
            tuple(row)
            for row in session.connection().exec_driver_sql("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
        ]
        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError("Private workspace identity mismatch")

        # Exclude vials already prepared or dosed; never offer corrections here.
        eligible = list(session.scalars(
            select(Vial).where(
                Vial.form == "lyophilized",
                Vial.volume_ml.is_(None),
                Vial.status.in_(("sealed", "in_use")),
                ~exists().where(
                    PreparationEvent.vial_id == Vial.id,
                ).where(PreparationEvent.kind == "reconstitution"),
                ~exists().where(DoseLog.vial_id == Vial.id),
            ).order_by(Vial.id.desc()).limit(100)
        ))
        options = [
            {
                "id": vial.id,
                "label": (
                    vial.compound.name + " · " +
                    (vial.label or f"Vial #{vial.id}")
                )[:240],
                "content_value": float(vial.content_value),
                "content_unit": vial.content_unit,
            }
            for vial in eligible
        ]
    return _response(uid, "options", options=options)


def private_reconstitute436(uid, private, payload):
    if os.getenv("TRACKER_WORKER_RECONSTITUTION_WRITE436") != "1":
        raise PermissionError("Private reconstitution writes disabled")

    payload = validate_payload436(payload)
    SessionLocal = _verified_storage(uid, private)

    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError
    from . import idempotency
    from .models import Vial, DoseLog, PreparationEvent

    with SessionLocal() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private inventory is busy") from exc

        marker = [
            tuple(row)
            for row in session.connection().exec_driver_sql("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
        ]
        if marker != [(uid, "inactive", 426)]:
            session.rollback()
            raise RuntimeError("Private workspace identity changed")

        state, digest = idempotency.check(
            session, payload["submission_token"], OPERATION, {
                "vial_id": payload["vial_id"],
                "volume_ml": payload["volume_ml"],
            },
        )
        if state != "new":
            session.rollback()
            return _response(uid, "duplicate")

        vial = session.get(Vial, payload["vial_id"])
        if (
            vial is None
            or vial.form != "lyophilized"
            or vial.status not in ("sealed", "in_use")
            or vial.volume_ml is not None
        ):
            session.rollback()
            return _response(uid, "rejected", error="Vial is unavailable for reconstitution")

        has_event = session.scalar(
            select(PreparationEvent.id)
            .where(PreparationEvent.vial_id == vial.id)
            .where(PreparationEvent.kind == "reconstitution")
            .limit(1)
        )
        has_dose = session.scalar(
            select(DoseLog.id)
            .where(DoseLog.vial_id == vial.id)
            .limit(1)
        )
        if has_event is not None or has_dose is not None:
            session.rollback()
            return _response(
                uid, "rejected",
                error="Existing reconstitution or dose history requires the correction workflow",
            )

        volume_ml = payload["volume_ml"]
        event = PreparationEvent(
            vial_id=vial.id,
            kind="reconstitution",
            notes=f"Added {volume_ml:g} mL; no supplies deducted (secondary pilot)",
        )
        session.add(event)
        vial.volume_ml = volume_ml
        vial.reconstituted_on = date.today()
        if vial.status == "sealed":
            vial.status = "in_use"
        idempotency.record(
            session, payload["submission_token"], OPERATION, digest,
        )
        session.flush()
        eid = event.id
        session.commit()
        return _response(uid, "created", record_id=eid)


def request_reconstitution436(user_id, action, payload=None, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if (
        config.instance_label() not in ("DEV", "PROD")
        or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1"
        or os.getenv("TRACKER_SECONDARY_RECONSTITUTION_WRITES436") != "1"
    ):
        raise PermissionError("Secondary reconstitution disabled")
    if type(action) is not str or action not in ACTIONS:
        raise ValueError("Unsupported reconstitution operation")

    uid = secondary_id(user_id)
    if action == "options":
        if payload is not None:
            raise ValueError("Options do not accept a payload")
        body = {"action": "options"}
    else:
        body = {"action": "reconstitute", "payload": validate_payload436(payload)}

    env = worker_environment428(uid, data_root)
    if action == "reconstitute":
        env["TRACKER_WORKER_RECONSTITUTION_WRITE436"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_reconstitution436"],
        input=json.dumps(body, separators=(",", ":"), allow_nan=False),
        cwd=SOURCE_ROOT, env=env,
        text=True, capture_output=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Private reconstitution worker failed (exit "
            + str(result.returncode) + "): " + result.stderr[-1200:]
        )

    try:
        report = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid reconstitution worker response") from exc

    if (
        type(report) is not dict
        or report.get("mode") != "private-reconstitution436"
        or report.get("user_id") != uid
        or report.get("login_enabled") is not False
        or report.get("http_listener_started") is not False
    ):
        raise RuntimeError("Reconstitution worker identity mismatch")

    if action == "options":
        options = report.get("options")
        if (
            report.get("status") != "options"
            or type(options) is not list
            or len(options) > 100
            or any(
                type(item) is not dict
                or set(item) != {
                    "id", "label", "content_value", "content_unit",
                }
                or type(item["id"]) is not int
                or type(item["label"]) is not str
                or len(item["label"]) > 240
                or type(item["content_value"]) not in (int, float)
                or not math.isfinite(item["content_value"])
                or item["content_value"] <= 0
                or type(item["content_unit"]) is not str
                for item in options
            )
        ):
            raise RuntimeError("Malformed reconstitution options")
    elif (
        report.get("status") not in ("created", "rejected", "duplicate")
        or type(report.get("written")) is not bool
        or report["written"] != (report["status"] == "created")
        or (
            report["status"] == "created"
            and type(report.get("id")) is not int
        )
        or (
            report["status"] == "rejected"
            and (
                type(report.get("error")) is not str
                or len(report["error"]) > 180
            )
        )
    ):
        raise RuntimeError("Malformed reconstitution write report")
    return report


def main():
    uid, private = validate_environment()
    action, payload = parse_request436(sys.stdin.buffer.read(MAX_BYTES + 1))
    report = (
        private_options436(uid, private)
        if action == "options"
        else private_reconstitute436(uid, private, payload)
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
