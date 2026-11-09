"""Release 438: isolated read-only supplies and DEV-gated private intake.

Every Supply requires a Purchase FK. A single internal purchase bucket is
created transactionally in each secondary workspace, never in the admin DB.
No supply usage or dose modification is performed by this worker.
"""
import json
import math
import os
import re
import subprocess
import sys
import uuid
from datetime import date

from .instance_parity523 import interactive_parity523
from .worker_dose_write434 import _verified_storage
from .worker_probe428 import validate_environment

KINDS = ("bac_water", "needle", "syringe", "swab", "empty_vial",
         "pen_cartridge", "other_supply")
COUNT_KINDS = frozenset(KINDS) - {"bac_water"}
FIELDS = frozenset(("name", "kind", "quantity", "notes", "submission_token"))
MAX_REQUEST = 4096
BUCKET = "secondary-supply-intake438"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate supply request field")
        result[key] = value
    return result


def validate_create438(payload):
    if type(payload) is not dict or set(payload) != FIELDS:
        raise ValueError("Unexpected supply fields")
    name, kind, quantity, notes, token = (payload[k] for k in
        ("name", "kind", "quantity", "notes", "submission_token"))
    if type(name) is not str or not 1 <= len(name.strip()) <= 160:
        raise ValueError("Invalid supply name")
    if type(kind) is not str or kind not in KINDS:
        raise ValueError("Unsupported supply category")
    if (type(quantity) not in (int, float)
        or not math.isfinite(quantity) or not 0 < quantity <= 1_000_000):
        raise ValueError("Invalid supply quantity")
    if kind in COUNT_KINDS and not float(quantity).is_integer():
        raise ValueError("Counted supplies require whole quantities")
    if (type(notes) is not str or len(notes) > 2000
        or any(ord(ch) < 32 and ch not in "\n\t" for ch in name + notes)):
        raise ValueError("Invalid supply notes")
    if type(token) is not str:
        raise ValueError("Invalid supply submission token")
    try:
        parsed = uuid.UUID(token)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid supply submission token") from exc
    if parsed.version != 4 or str(parsed) != token:
        raise ValueError("Invalid supply submission token")
    return dict(name=name.strip(), kind=kind, quantity=float(quantity),
                notes=notes.strip(), submission_token=token)


def parse_request438(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("Invalid supply request size")
    try:
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid supply request") from exc
    if type(request) is not dict or type(request.get("action")) is not str:
        raise ValueError("Invalid supply request")
    if request["action"] == "list" and set(request) == {"action"}:
        return "list", None
    if request["action"] == "create" and set(request) == {"action", "payload"}:
        return "create", validate_create438(request["payload"])
    raise ValueError("Unsupported supply request")


def form_create438(form):
    expected = FIELDS | {"csrf_token"}
    if set(form) != expected or any(len(form.getlist(k)) != 1 for k in expected):
        raise ValueError("Unexpected or repeated supply form fields")
    value = str(form["quantity"]).strip()
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,4})?", value):
        raise ValueError("Invalid supply quantity")
    payload = {k: str(form[k]).strip() for k in FIELDS}
    payload["quantity"] = float(value)
    return validate_create438(payload)


def _check(session, uid):
    rows = [tuple(row) for row in session.connection().exec_driver_sql("""
        SELECT user_id,status,schema_version FROM tracker_staged_workspace426
    """).fetchall()]
    if rows != [(uid, "inactive", 426)]:
        raise RuntimeError("Private supply workspace identity changed")


def _response(uid, status, **kwargs):
    return dict(mode="private-supplies438", user_id=uid, status=status,
                login_enabled=False, http_listener_started=False, **kwargs)


def private_list438(uid, private):
    from sqlalchemy import select
    from .models import Supply
    Local = _verified_storage(uid, private)
    with Local() as session:
        _check(session, uid)
        supplies = list(session.scalars(
            select(Supply).order_by(Supply.id.desc()).limit(150)))
        rows = [dict(
            id=s.id, name=s.name, kind=s.kind,
            quantity=float(s.purchased_qty),
            remaining=float(s.remaining_qty),
            unit="mL" if s.kind == "bac_water" else "count",
        ) for s in supplies]
    return _response(uid, "list", supplies=rows)


def private_create438(uid, private, payload):
    if os.getenv("TRACKER_WORKER_SUPPLY_WRITES438") != "1":
        raise PermissionError("Private supply intake disabled")
    payload = validate_create438(payload)
    Local = _verified_storage(uid, private)

    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError
    from .models import Supply, Purchase, ChangeAudit
    from . import idempotency
    from .supply_categories import ensure_categories, validate_supply

    with Local() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private supply inventory busy") from exc
        _check(session, uid)
        state, digest = idempotency.check(
            session, payload["submission_token"], "secondary_supply_intake438",
            {k: v for k, v in payload.items() if k != "submission_token"})
        if state != "new":
            session.rollback()
            return _response(uid, "duplicate", written=False)

        ensure_categories(session)
        validate_supply(session, payload["kind"], payload["quantity"])
        purchase = session.scalar(
            select(Purchase).where(Purchase.order_ref == BUCKET).limit(1))
        if purchase is None:
            purchase = Purchase(
                vendor="Secondary Supply Intake", purchased_on=date.today(),
                order_ref=BUCKET, shipping_cents=0,
                tax_cents=0, discount_cents=0,
                notes="Internal inventory intake; not a vendor order")
            session.add(purchase)
            session.flush()
        item = Supply(
            purchase_id=purchase.id, name=payload["name"],
            kind=payload["kind"], purchased_qty=payload["quantity"],
            remaining_qty=payload["quantity"], unit_price_cents=0,
            notes=payload["notes"])
        session.add(item)
        session.flush()
        session.add(ChangeAudit(
            entity_type="supply", entity_id=item.id,
            action="secondary_supply_intake438",
            before_json="{}",
            after_json=json.dumps(dict(
                name=item.name, kind=item.kind,
                quantity=item.purchased_qty,
                remaining=item.remaining_qty), sort_keys=True)))
        idempotency.record(
            session, payload["submission_token"],
            "secondary_supply_intake438", digest)
        session.commit()
        return _response(uid, "created", written=True, id=item.id)


def request_supply438(user_id, action, payload=None, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if (not interactive_parity523()
        or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1"):
        raise PermissionError("Private supply preview disabled")
    if type(action) is not str or action not in ("list", "create"):
        raise ValueError("Unsupported supply operation")
    if action == "list" and payload is not None:
        raise ValueError("List cannot have a payload")
    if action == "create":
        if os.getenv("TRACKER_SECONDARY_SUPPLY_WRITES438") != "1":
            raise PermissionError("Private supply intake disabled")
        payload = validate_create438(payload)
    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)
    if action == "create":
        env["TRACKER_WORKER_SUPPLY_WRITES438"] = "1"
    request = {"action": action}
    if payload is not None:
        request["payload"] = payload
    proc = subprocess.run(
        [sys.executable, "-m", "app.worker_supply438"],
        input=json.dumps(request, separators=(",", ":"), allow_nan=False),
        cwd=SOURCE_ROOT, env=env, capture_output=True,
        text=True, timeout=45, check=False)
    if proc.returncode:
        raise RuntimeError(
            f"Private supply worker failed ({proc.returncode}): "
            + proc.stderr[-1100:])
    try:
        answer = json.loads(proc.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid supply worker response") from exc
    if (type(answer) is not dict
        or answer.get("mode") != "private-supplies438"
        or answer.get("user_id") != uid
        or answer.get("login_enabled") is not False
        or answer.get("http_listener_started") is not False):
        raise RuntimeError("Private supply worker identity mismatch")
    if action == "list":
        rows = answer.get("supplies")
        if (answer.get("status") != "list" or type(rows) is not list
            or len(rows) > 150):
            raise RuntimeError("Malformed private supply list")
        for item in rows:
            if (type(item) is not dict
                or set(item) != {"id","name","kind","quantity","remaining","unit"}
                or type(item["id"]) is not int
                or type(item["name"]) is not str
                or item["kind"] not in KINDS
                or item["unit"] not in ("mL","count")
                or any(type(item[k]) not in (int,float) or not math.isfinite(item[k])
                       for k in ("quantity","remaining"))):
                raise RuntimeError("Malformed supply inventory item")
    elif (answer.get("status") not in ("created","duplicate")
          or type(answer.get("written")) is not bool
          or answer["written"] != (answer["status"] == "created")
          or (answer["status"] == "created"
              and type(answer.get("id")) is not int)):
        raise RuntimeError("Malformed supply intake response")
    return answer


def main():
    uid, private = validate_environment()
    action, payload = parse_request438(sys.stdin.buffer.read(MAX_REQUEST + 1))
    answer = (private_list438(uid, private) if action == "list"
              else private_create438(uid, private, payload))
    print(json.dumps(answer, sort_keys=True))


if __name__ == "__main__":
    main()
