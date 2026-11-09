"""Release 435: isolated secondary inventory listing and create-only operations.

No arbitrary SQL, caller-selected account, edit/delete, or purchase mutation.
Identity and private SQLite paths are verified independently in each worker.
"""

import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from urllib.parse import quote

from .worker_probe428 import validate_environment
from .worker_read429 import private_overview429

MAX_BYTES = 4096
OPERATIONS = frozenset(("inventory", "create_compound", "create_vial"))
COMPOUND_KEYS = frozenset((
    "name", "category", "primary_unit", "notes", "submission_token",
))
VIAL_KEYS = frozenset((
    "compound_id", "label", "content_value", "content_unit",
    "form", "volume_ml", "lot", "cap_color", "notes", "submission_token",
))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate private inventory field")
        result[key] = value
    return result


def _text(value, max_length, *, required=False):
    if type(value) is not str:
        raise ValueError("Invalid text value")
    value = value.strip()
    if (
        len(value) > max_length
        or (required and not value)
        or any(ord(ch) < 32 and ch not in "\t\n" for ch in value)
    ):
        raise ValueError("Invalid text value")
    return value


def _token(value):
    if type(value) is not str:
        raise ValueError("Invalid submission token")
    try:
        token = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid submission token") from exc
    if token.version != 4 or str(token) != value:
        raise ValueError("Invalid submission token")
    return value


def validate_inventory435(action, payload):
    from .models import CATEGORIES, VIAL_FORMS
    from . import units

    if action == "create_compound":
        if type(payload) is not dict or set(payload) != COMPOUND_KEYS:
            raise ValueError("Unexpected compound fields")
        name = _text(payload["name"], 120, required=True)
        category = payload["category"]
        primary = payload["primary_unit"]
        if type(category) is not str or category not in CATEGORIES:
            raise ValueError("Unknown compound category")
        if type(primary) is not str or primary not in units.CONTENT_UNITS:
            raise ValueError("Unknown primary unit")
        if name.casefold() in (
            "somatropin", "somatropin (hgh)", "hgh (somatropin)",
        ) and primary != "IU":
            raise ValueError("Somatropin must be tracked in IU")
        return {
            "name": name, "category": category, "primary_unit": primary,
            "notes": _text(payload["notes"], 2000),
            "submission_token": _token(payload["submission_token"]),
        }

    if action == "create_vial":
        if type(payload) is not dict or set(payload) != VIAL_KEYS:
            raise ValueError("Unexpected vial fields")
        cid = payload["compound_id"]
        if type(cid) is not int or not 1 <= cid <= 2147483647:
            raise ValueError("Invalid compound selection")
        amount = payload["content_value"]
        if (
            type(amount) not in (int, float)
            or not math.isfinite(amount)
            or not 0 < amount <= 1000000
        ):
            raise ValueError("Invalid vial content")
        unit = payload["content_unit"]
        if type(unit) is not str or unit not in units.CONTENT_UNITS:
            raise ValueError("Invalid vial content unit")
        form = payload["form"]
        if type(form) is not str or form not in VIAL_FORMS:
            raise ValueError("Invalid vial form")

        volume = payload["volume_ml"]
        if volume is not None and (
            type(volume) not in (int, float)
            or not math.isfinite(volume)
            or not 0 < volume <= 10000
        ):
            raise ValueError("Invalid vial volume")
        if form == "solution" and volume is None:
            raise ValueError("Liquid vials require a volume")
        if form == "lyophilized" and volume is not None:
            raise ValueError("Reconstitute lyophilized vials separately")
        return {
            "compound_id": cid,
            "label": _text(payload["label"], 160),
            "content_value": float(amount),
            "content_unit": unit, "form": form,
            "volume_ml": float(volume) if volume is not None else None,
            "lot": _text(payload["lot"], 80),
            "cap_color": _text(payload["cap_color"], 60),
            "notes": _text(payload["notes"], 2000),
            "submission_token": _token(payload["submission_token"]),
        }
    raise ValueError("Unsupported inventory operation")


def parse_request435(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid private inventory request size")
    try:
        msg = json.loads(
            raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private inventory JSON") from exc
    if type(msg) is not dict or type(msg.get("action")) is not str:
        raise ValueError("Invalid inventory request")
    action = msg["action"]
    if action not in OPERATIONS:
        raise ValueError("Unsupported inventory operation")
    if action == "inventory":
        if set(msg) != {"action"}:
            raise ValueError("Unexpected inventory list fields")
        return action, None
    if set(msg) != {"action", "payload"}:
        raise ValueError("Unexpected inventory request fields")
    return action, validate_inventory435(action, msg["payload"])


def _form_values(form, names):
    expected = set(names) | {"csrf_token", "submission_token"}
    if set(form) != expected or any(len(form.getlist(k)) != 1 for k in expected):
        raise ValueError("Unexpected or repeated inventory form fields")
    return {name: str(form[name]).strip() for name in names}


def form_compound435(form):
    fields = _form_values(form, ("name", "category", "primary_unit", "notes"))
    fields["submission_token"] = str(form["submission_token"]).strip()
    return validate_inventory435("create_compound", fields)


def form_vial435(form):
    fields = _form_values(form, (
        "compound_id", "label", "content_value", "content_unit",
        "form", "volume_ml", "lot", "cap_color", "notes",
    ))
    if not re.fullmatch(r"[1-9]\d{0,9}", fields["compound_id"]):
        raise ValueError("Invalid compound selection")
    number = fields["content_value"]
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,6})?", number):
        raise ValueError("Invalid vial content")
    volume = fields["volume_ml"]
    if volume and not re.fullmatch(r"\d{1,5}(?:\.\d{1,4})?", volume):
        raise ValueError("Invalid vial volume")
    fields["compound_id"] = int(fields["compound_id"])
    fields["content_value"] = float(number)
    fields["volume_ml"] = float(volume) if volume else None
    fields["submission_token"] = str(form["submission_token"]).strip()
    return validate_inventory435("create_vial", fields)


def _check_private(uid, private):
    private_overview429(uid, private)
    return private / "tracker.db"


def private_list435(uid, private):
    database = _check_private(uid, private)
    uri = "file:" + quote(str(database), safe="/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        conn.execute("PRAGMA query_only=ON")
        marker = conn.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError("Private workspace identity mismatch")
        compounds = [
            {"id": row[0], "name": row[1],
             "category": row[2], "primary_unit": row[3]}
            for row in conn.execute("""
                SELECT id,name,category,primary_unit
                FROM compounds ORDER BY name COLLATE NOCASE,id LIMIT 200
            """)
        ]
        vials = [
            {
                "id": row[0], "compound_id": row[1],
                "compound": row[2], "label": row[3],
                "content_value": row[4], "content_unit": row[5],
                "status": row[6], "form": row[7],
            }
            for row in conn.execute("""
                SELECT v.id,v.compound_id,c.name,v.label,v.content_value,
                       v.content_unit,v.status,v.form
                FROM vials AS v JOIN compounds AS c ON c.id=v.compound_id
                ORDER BY v.id DESC LIMIT 200
            """)
        ]
    return {
        "mode": "private-inventory435", "status": "inventory",
        "user_id": uid, "compounds": compounds, "vials": vials,
        "login_enabled": False, "http_listener_started": False,
    }


def private_create435(uid, private, action, payload):
    if os.getenv("TRACKER_WORKER_INVENTORY_WRITE435") != "1":
        raise PermissionError("Private inventory writes disabled")
    validate_inventory435(action, payload)
    _check_private(uid, private)

    from . import idempotency, units, db
    from .models import Compound, Vial
    from sqlalchemy import select, func
    from sqlalchemy.exc import IntegrityError, OperationalError

    operation = "secondary_" + action + "435"
    with db.SessionLocal() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private inventory busy") from exc

        marker = [
            tuple(r) for r in session.connection().exec_driver_sql("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
        ]
        if marker != [(uid, "inactive", 426)]:
            session.rollback()
            raise RuntimeError("Private workspace identity mismatch")

        state, digest = idempotency.check(
            session, payload["submission_token"], operation,
            {k: v for k, v in payload.items() if k != "submission_token"},
        )
        if state != "new":
            session.rollback()
            return _write_result(uid, "duplicate")

        if action == "create_compound":
            existing = session.scalar(
                select(Compound.id)
                .where(func.lower(Compound.name) == payload["name"].lower())
                .limit(1)
            )
            if existing:
                session.rollback()
                return _write_result(uid, "rejected", "Compound already exists")
            record = Compound(
                name=payload["name"], category=payload["category"],
                primary_unit=payload["primary_unit"], notes=payload["notes"],
            )
        else:
            compound = session.get(Compound, payload["compound_id"])
            if compound is None:
                session.rollback()
                return _write_result(uid, "rejected", "Compound unavailable")
            if (units.parse_unit(compound.primary_unit).dim
                    != units.parse_unit(payload["content_unit"]).dim):
                session.rollback()
                return _write_result(
                    uid, "rejected", "Vial and compound units are incompatible",
                )
            record = Vial(
                compound_id=compound.id,
                label=payload["label"], lot=payload["lot"],
                cap_color=payload["cap_color"], form=payload["form"],
                content_value=payload["content_value"],
                content_unit=payload["content_unit"],
                volume_ml=payload["volume_ml"], notes=payload["notes"],
                status="sealed", use_coa_content=False,
                unit_price_cents=0,
            )
        try:
            session.add(record)
            idempotency.record(
                session, payload["submission_token"], operation, digest,
            )
            session.flush()
            new_id = record.id
            session.commit()
        except IntegrityError:
            session.rollback()
            return _write_result(uid, "rejected", "Inventory entry already exists")
    return _write_result(uid, "created", record_id=new_id)


def _write_result(uid, status, error="", record_id=None):
    result = {
        "mode": "private-inventory435", "status": status, "user_id": uid,
        "written": status == "created",
        "login_enabled": False, "http_listener_started": False,
    }
    if status == "rejected":
        result["error"] = error
    if record_id is not None:
        result["id"] = record_id
    return result


def request_inventory435(user_id, action, payload=None, data_root=None):
    """Parent may read any verified private inventory; write is separately gated."""
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if config.instance_label() not in ("DEV", "PROD") or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1":
        raise PermissionError("Secondary preview disabled")
    if type(action) is not str or action not in OPERATIONS:
        raise ValueError("Unsupported inventory operation")
    if action == "inventory" and payload is not None:
        raise ValueError("Inventory listing accepts no payload")
    if action != "inventory":
        if os.getenv("TRACKER_SECONDARY_INVENTORY_WRITES435") != "1":
            raise PermissionError("Secondary inventory writes disabled")
        payload = validate_inventory435(action, payload)

    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)
    if action != "inventory":
        env["TRACKER_WORKER_INVENTORY_WRITE435"] = "1"

    request = {"action": action}
    if payload is not None:
        request["payload"] = payload

    proc = subprocess.run(
        [sys.executable, "-m", "app.worker_inventory435"],
        input=json.dumps(request, separators=(",", ":"), allow_nan=False),
        cwd=SOURCE_ROOT, env=env, capture_output=True, text=True,
        timeout=45, check=False,
    )
    if proc.returncode:
        raise RuntimeError(
            "Private inventory worker failed (exit "
            + str(proc.returncode) + "): " + proc.stderr[-1100:]
        )
    try:
        result = json.loads(proc.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid private inventory JSON") from exc

    if (
        type(result) is not dict
        or result.get("mode") != "private-inventory435"
        or result.get("user_id") != uid
        or result.get("login_enabled") is not False
        or result.get("http_listener_started") is not False
    ):
        raise RuntimeError("Private inventory identity mismatch")

    if action == "inventory":
        compounds = result.get("compounds")
        vials = result.get("vials")
        if (
            result.get("status") != "inventory"
            or type(compounds) is not list or len(compounds) > 200
            or type(vials) is not list or len(vials) > 200
            or any(
                type(x) is not dict
                or set(x) != {"id", "name", "category", "primary_unit"}
                for x in compounds
            )
            or any(
                type(x) is not dict
                or set(x) != {
                    "id", "compound_id", "compound", "label",
                    "content_value", "content_unit", "status", "form",
                }
                for x in vials
            )
        ):
            raise RuntimeError("Private inventory response malformed")
    else:
        status = result.get("status")
        if (
            status not in ("created", "duplicate", "rejected")
            or type(result.get("written")) is not bool
            or result["written"] != (status == "created")
            or (status == "created" and type(result.get("id")) is not int)
            or (status == "rejected" and (
                type(result.get("error")) is not str
                or len(result["error"]) > 180
            ))
        ):
            raise RuntimeError("Private inventory write response malformed")
    return result


def main():
    uid, private = validate_environment()
    action, payload = parse_request435(sys.stdin.buffer.read(MAX_BYTES + 1))
    response = (
        private_list435(uid, private)
        if action == "inventory"
        else private_create435(uid, private, action, payload)
    )
    print(json.dumps(response, sort_keys=True))


if __name__ == "__main__":
    main()
