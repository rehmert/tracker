"""Release 437: private vial reconciliation and audited metadata/lifecycle correction.

The HTTP user never selects a database. The independent child validates its
private workspace before reading, then reserves SQLite BEGIN IMMEDIATE before
a correction. No content, concentration, dose, or supply quantities can change.
"""

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from .instance_parity523 import interactive_parity523
import uuid

MAX_BYTES = 4096
ACTIONS = frozenset(("report", "detail", "correct"))
EDIT_FIELDS = frozenset((
    "vial_id", "snapshot", "label", "lot", "cap_color",
    "status", "reason", "submission_token",
))
STATES = frozenset(("sealed", "in_use", "finished", "discarded"))
OPERATION = "secondary_vial_correction437"


def _distinct(pairs):
    values = {}
    for name, value in pairs:
        if name in values:
            raise ValueError("Duplicate private vial field")
        values[name] = value
    return values


def _text(value, max_len, *, required=False):
    if type(value) is not str:
        raise ValueError("Invalid correction text")
    value = value.strip()
    if (
        (required and not value)
        or len(value) > max_len
        or any(ord(ch) < 32 and ch not in "\n\t" for ch in value)
    ):
        raise ValueError("Invalid correction text")
    return value


def _uid(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError("Invalid vial ID")
    return value


def _token(value):
    if type(value) is not str:
        raise ValueError("Invalid submission identifier")
    try:
        token = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid submission identifier") from exc
    if token.version != 4 or str(token) != value:
        raise ValueError("Invalid submission identifier")
    return value


def validate_correction437(payload):
    if type(payload) is not dict or set(payload) != EDIT_FIELDS:
        raise ValueError("Unexpected correction fields")
    status = payload["status"]
    if type(status) is not str or status not in STATES:
        raise ValueError("Unknown vial status")
    snapshot = payload["snapshot"]
    if type(snapshot) is not str or not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        raise ValueError("Invalid vial snapshot")
    reason = _text(payload["reason"], 400, required=True)
    if len(reason) < 8:
        raise ValueError("Correction reason must be at least 8 characters")
    return {
        "vial_id": _uid(payload["vial_id"]),
        "snapshot": snapshot,
        "label": _text(payload["label"], 160),
        "lot": _text(payload["lot"], 80),
        "cap_color": _text(payload["cap_color"], 60),
        "status": status,
        "reason": reason,
        "submission_token": _token(payload["submission_token"]),
    }


def parse_request437(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid private reconciliation request size")
    try:
        item = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_distinct,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private reconciliation JSON") from exc
    if type(item) is not dict or type(item.get("action")) is not str:
        raise ValueError("Invalid private reconciliation request")

    action = item["action"]
    if action == "report" and set(item) == {"action"}:
        return action, None

    if action == "detail" and set(item) == {"action", "vial_id"}:
        return action, _uid(item["vial_id"])

    if action == "correct" and set(item) == {"action", "payload"}:
        return action, validate_correction437(item["payload"])

    raise ValueError("Unsupported reconciliation operation")


def form_correction437(form):
    names = EDIT_FIELDS | {"csrf_token"}
    if set(form) != names or any(len(form.getlist(key)) != 1 for key in names):
        raise ValueError("Unexpected or repeated correction form field")
    raw_id = str(form["vial_id"]).strip()
    if not re.fullmatch(r"[1-9]\d{0,9}", raw_id):
        raise ValueError("Invalid vial selection")
    return validate_correction437({
        name: int(raw_id) if name == "vial_id" else str(form[name]).strip()
        for name in EDIT_FIELDS
    })


def _session_for_private(uid, private):
    from .worker_dose_write434 import _verified_storage
    return _verified_storage(uid, private)


def _marker(session, uid):
    rows = [
        tuple(row) for row in session.connection().exec_driver_sql("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
    ]
    if rows != [(uid, "inactive", 426)]:
        raise RuntimeError("Private workspace identity mismatch")


def _metadata(vial):
    return {
        "label": vial.label or "",
        "lot": vial.lot or "",
        "cap_color": vial.cap_color or "",
        "status": vial.status,
    }


def _audit_ordinal(session, vid):
    from sqlalchemy import func, select
    from .models import ChangeAudit, DoseLog, PreparationEvent, BlendComponent
    audit = session.scalar(
        select(func.max(ChangeAudit.id)).where(
            ChangeAudit.entity_type == "vial",
            ChangeAudit.entity_id == vid,
        )
    ) or 0
    dose = session.scalar(
        select(func.max(DoseLog.id)).where(DoseLog.vial_id == vid)
    ) or 0
    prep = session.scalar(
        select(func.max(PreparationEvent.id))
        .where(PreparationEvent.vial_id == vid)
    ) or 0
    transfer = session.scalar(
        select(func.max(BlendComponent.id))
        .where(BlendComponent.source_vial_id == vid)
    ) or 0
    return [audit, dose, prep, transfer]


def _snapshot(vial, view, ordinals):
    state = {
        "id": vial.id,
        "metadata": _metadata(vial),
        "content_value": vial.content_value,
        "content_unit": vial.content_unit,
        "form": vial.form,
        "volume_ml": vial.volume_ml,
        "reconstituted_on": (
            vial.reconstituted_on.isoformat()
            if vial.reconstituted_on else None
        ),
        "remaining_base": view.remaining_base,
        "consumed_base": view.consumed_base,
        "content_base": view.content_base,
        "ordinals": ordinals,
    }
    encoded = json.dumps(
        state, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _row(session, vial):
    from . import services, units
    from sqlalchemy import func, select
    from .models import DoseLog, PreparationEvent

    view = services.vial_views(session, [vial])[vial.id]
    if not all(math.isfinite(n) for n in (
        view.content_base, view.consumed_base, view.remaining_base,
        view.over_base,
    )):
        raise RuntimeError("Nonfinite private inventory amounts")

    ordinals = _audit_ordinal(session, vial.id)
    unit = vial.content_unit
    total = units.from_base(view.content_base, unit)
    used = units.from_base(view.consumed_base, unit)
    remaining = units.from_base(view.remaining_base, unit)
    overdraw = units.from_base(view.over_base, unit)
    dose_count = session.scalar(
        select(func.count(DoseLog.id)).where(DoseLog.vial_id == vial.id)
    ) or 0
    prep_count = session.scalar(
        select(func.count(PreparationEvent.id)).where(
            PreparationEvent.vial_id == vial.id,
            PreparationEvent.kind == "reconstitution",
        )
    ) or 0

    warnings = []
    if overdraw > 0.000001:
        warnings.append("Usage exceeds recorded contents")
    if vial.status in ("sealed", "in_use") and view.remaining_base <= 1e-7:
        warnings.append("Active vial has no remaining stock")
    if vial.status in ("finished", "discarded") and view.remaining_base > 1e-7:
        warnings.append("Closed vial has unused recorded stock")
    if vial.status == "sealed" and (dose_count > 0 or prep_count > 0):
        warnings.append("Sealed status conflicts with recorded use")

    return {
        "id": vial.id,
        "compound": vial.compound.name,
        "label": vial.label or "",
        "lot": vial.lot or "",
        "cap_color": vial.cap_color or "",
        "status": vial.status,
        "unit": unit,
        "total": total,
        "used": used,
        "remaining": remaining,
        "overdraw": overdraw,
        "volume_ml": vial.volume_ml,
        "dose_count": int(dose_count),
        "reconstitution_count": int(prep_count),
        "warnings": warnings,
        "snapshot": _snapshot(vial, view, ordinals),
    }


def _audit_rows(session, vid):
    from sqlalchemy import select
    from .models import ChangeAudit
    events = list(session.scalars(
        select(ChangeAudit)
        .where(ChangeAudit.entity_type == "vial", ChangeAudit.entity_id == vid)
        .order_by(ChangeAudit.id.desc()).limit(15)
    ))
    data = []
    for event in events:
        try:
            before = json.loads(event.before_json or "{}")
            after = json.loads(event.after_json or "{}")
        except (ValueError, TypeError):
            before, after = {}, {}
        data.append({
            "id": event.id,
            "at": event.created_at.isoformat() if event.created_at else "",
            "action": event.action,
            "reason": str(after.get("_reason", ""))[:400],
            "before": {key: str(before.get(key, ""))[:160] for key in (
                "label", "lot", "cap_color", "status",
            )},
            "after": {key: str(after.get(key, ""))[:160] for key in (
                "label", "lot", "cap_color", "status",
            )},
        })
    return data


def _result(uid, status, **kwargs):
    return {
        "mode": "private-reconciliation437",
        "user_id": uid,
        "status": status,
        "login_enabled": False,
        "http_listener_started": False,
        **kwargs,
    }


def private_read437(uid, private, action, vid=None):
    from sqlalchemy import select
    from .models import Vial
    SessionLocal = _session_for_private(uid, private)
    with SessionLocal() as session:
        _marker(session, uid)
        if action == "report":
            vials = list(session.scalars(
                select(Vial).order_by(Vial.id.desc()).limit(100)
            ))
            return _result(
                uid, "report",
                items=[_row(session, vial) for vial in vials],
            )
        vial = session.get(Vial, vid)
        if vial is None:
            return _result(uid, "missing", item=None, audit=[])
        return _result(
            uid, "detail",
            item=_row(session, vial),
            audit=_audit_rows(session, vid),
        )


def _allowed_transition(old, new):
    if old == new:
        return True
    return (
        (old == "sealed" and new == "discarded")
        or (old == "in_use" and new in ("finished", "discarded"))
    )


def private_correct437(uid, private, payload):
    if os.getenv("TRACKER_WORKER_VIAL_CORRECTIONS437") != "1":
        raise PermissionError("Private vial corrections disabled")

    payload = validate_correction437(payload)
    SessionLocal = _session_for_private(uid, private)

    from sqlalchemy.exc import OperationalError
    from . import idempotency
    from .models import Vial, ChangeAudit

    with SessionLocal() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private inventory busy") from exc

        _marker(session, uid)
        state, digest = idempotency.check(
            session, payload["submission_token"], OPERATION,
            {k: v for k, v in payload.items() if k != "submission_token"},
        )
        if state != "new":
            session.rollback()
            return _result(uid, "duplicate", written=False)

        vial = session.get(Vial, payload["vial_id"])
        if vial is None:
            session.rollback()
            return _result(uid, "rejected", written=False, error="Vial unavailable")

        current = _row(session, vial)
        if current["snapshot"] != payload["snapshot"]:
            session.rollback()
            return _result(uid, "stale", written=False)

        before = _metadata(vial)
        after = {
            key: payload[key] for key in (
                "label", "lot", "cap_color", "status",
            )
        }
        if before == after:
            session.rollback()
            return _result(
                uid, "rejected", written=False, error="Nothing has changed",
            )
        if not _allowed_transition(before["status"], after["status"]):
            session.rollback()
            return _result(
                uid, "rejected", written=False, error="Unsafe lifecycle transition",
            )

        for key, value in after.items():
            setattr(vial, key, value)

        session.add(ChangeAudit(
            entity_type="vial",
            entity_id=vial.id,
            action="secondary_correction437",
            before_json=json.dumps(before, sort_keys=True),
            after_json=json.dumps({
                **after, "_reason": payload["reason"],
            }, sort_keys=True),
        ))
        idempotency.record(
            session, payload["submission_token"], OPERATION, digest,
        )
        session.flush()
        session.commit()
        return _result(uid, "created", written=True, id=vial.id)


def request_reconciliation437(user_id, action, *, vial_id=None,
                              payload=None, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if (
        not interactive_parity523()
        or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1"
    ):
        raise PermissionError("Private reconciliation disabled")

    if type(action) is not str or action not in ACTIONS:
        raise ValueError("Unsupported reconciliation action")
    if action == "report" and (vial_id is not None or payload is not None):
        raise ValueError("Report cannot select a workspace or vial")
    if action == "detail" and (payload is not None or vial_id is None):
        raise ValueError("Detail requires only a vial ID")
    if action == "correct":
        if vial_id is not None:
            raise ValueError("Correction cannot select a second vial")
        if os.getenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437") != "1":
            raise PermissionError("Private vial corrections disabled")
        payload = validate_correction437(payload)

    uid = secondary_id(user_id)
    request = {"action": action}
    if action == "detail":
        request["vial_id"] = _uid(vial_id)
    elif action == "correct":
        request["payload"] = payload

    env = worker_environment428(uid, data_root)
    if action == "correct":
        env["TRACKER_WORKER_VIAL_CORRECTIONS437"] = "1"

    process = subprocess.run(
        [sys.executable, "-m", "app.worker_reconciliation437"],
        input=json.dumps(
            request, separators=(",", ":"), allow_nan=False,
        ),
        cwd=SOURCE_ROOT, env=env,
        capture_output=True, text=True, timeout=45, check=False,
    )
    if process.returncode:
        raise RuntimeError(
            "Private reconciliation worker failed (exit "
            + str(process.returncode) + "): " + process.stderr[-1200:]
        )
    try:
        answer = json.loads(process.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid reconciliation JSON") from exc

    if (
        type(answer) is not dict
        or answer.get("mode") != "private-reconciliation437"
        or answer.get("user_id") != uid
        or answer.get("login_enabled") is not False
        or answer.get("http_listener_started") is not False
    ):
        raise RuntimeError("Private reconciliation worker identity mismatch")

    status = answer.get("status")
    if action == "report":
        rows = answer.get("items")
        if status != "report" or type(rows) is not list or len(rows) > 100:
            raise RuntimeError("Invalid reconciliation report")
        for item in rows:
            _validate_row(item)
    elif action == "detail":
        if status not in ("detail", "missing"):
            raise RuntimeError("Invalid reconciliation detail")
        if status == "detail":
            _validate_row(answer.get("item"))
            events = answer.get("audit")
            if type(events) is not list or len(events) > 15:
                raise RuntimeError("Invalid reconciliation audit")
        elif answer.get("item") is not None:
            raise RuntimeError("Invalid missing-vial response")
    else:
        if (
            status not in ("created", "duplicate", "stale", "rejected")
            or type(answer.get("written")) is not bool
            or answer["written"] != (status == "created")
            or (status == "created" and type(answer.get("id")) is not int)
            or (
                status == "rejected" and (
                    type(answer.get("error")) is not str
                    or len(answer["error"]) > 180
                )
            )
        ):
            raise RuntimeError("Invalid reconciliation correction response")
    return answer


def _validate_row(item):
    if type(item) is not dict or set(item) != {
        "id", "compound", "label", "lot", "cap_color", "status", "unit",
        "total", "used", "remaining", "overdraw", "volume_ml",
        "dose_count", "reconstitution_count", "warnings", "snapshot",
    }:
        raise RuntimeError("Invalid reconciliation row")
    if (
        type(item["id"]) is not int
        or any(type(item[key]) is not str for key in (
            "compound", "label", "lot", "cap_color", "status", "unit", "snapshot",
        ))
        or item["status"] not in STATES
        or not re.fullmatch(r"[0-9a-f]{64}", item["snapshot"])
        or any(
            type(item[key]) not in (float, int)
            or not math.isfinite(item[key])
            for key in ("total", "used", "remaining", "overdraw")
        )
        or type(item["dose_count"]) is not int
        or type(item["reconstitution_count"]) is not int
        or type(item["warnings"]) is not list
        or len(item["warnings"]) > 4
        or any(type(value) is not str for value in item["warnings"])
    ):
        raise RuntimeError("Invalid reconciliation row values")


def main():
    from .worker_probe428 import validate_environment
    uid, private = validate_environment()
    action, value = parse_request437(sys.stdin.buffer.read(MAX_BYTES + 1))
    if action == "correct":
        result = private_correct437(uid, private, value)
    else:
        result = private_read437(uid, private, action, value)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
