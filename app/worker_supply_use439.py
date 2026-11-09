"""Release 439: explicit, auditable supply use in a verified private workspace.

No generic SQL, workspace selector, automatic consumption, or dose editing.
One existing dose/reconstitution is linked per write, under BEGIN IMMEDIATE.
"""
import json
import math
import os
import re
import subprocess
import sys
import uuid

from .worker_dose_write434 import _verified_storage
from .worker_probe428 import validate_environment
from .worker_supply438 import KINDS, COUNT_KINDS

MAX_BYTES = 4096
FIELDS = frozenset((
    "supply_id", "reference_type", "reference_id",
    "amount", "notes", "submission_token",
))
OPERATION = "secondary_supply_use439"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate supply-use field")
        result[key] = value
    return result


def _identifier(value):
    return type(value) is int and 1 <= value <= 2147483647


def validate_use439(payload):
    if type(payload) is not dict or set(payload) != FIELDS:
        raise ValueError("Unexpected supply-use fields")
    for name in ("supply_id", "reference_id"):
        if not _identifier(payload[name]):
            raise ValueError("Invalid " + name)
    if (type(payload["reference_type"]) is not str
        or payload["reference_type"] not in ("dose", "reconstitution")):
        raise ValueError("Unsupported supply reference")
    amount = payload["amount"]
    if (type(amount) not in (int, float)
        or not math.isfinite(amount) or not 0 < amount <= 1000000):
        raise ValueError("Invalid supply-use amount")
    notes = payload["notes"]
    if (type(notes) is not str or len(notes) > 400
        or any(ord(char) < 32 and char not in "\t\n" for char in notes)):
        raise ValueError("Invalid supply-use notes")
    token = payload["submission_token"]
    if type(token) is not str:
        raise ValueError("Invalid submission token")
    try:
        parsed = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid submission token") from exc
    if parsed.version != 4 or str(parsed) != token:
        raise ValueError("Invalid submission token")
    return {
        "supply_id": payload["supply_id"],
        "reference_type": payload["reference_type"],
        "reference_id": payload["reference_id"],
        "amount": float(amount), "notes": notes.strip(),
        "submission_token": token,
    }


def parse_request439(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid supply-use request size")
    try:
        request = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid supply-use JSON") from exc
    if type(request) is not dict or type(request.get("action")) is not str:
        raise ValueError("Invalid supply-use request")
    if request["action"] == "options" and set(request) == {"action"}:
        return "options", None
    if request["action"] == "use" and set(request) == {"action", "payload"}:
        return "use", validate_use439(request["payload"])
    raise ValueError("Unsupported supply-use action")


def form_use439(form):
    expected = frozenset((
        "csrf_token", "submission_token", "supply_id",
        "reference", "amount", "notes",
    ))
    if set(form) != expected or any(len(form.getlist(k)) != 1 for k in expected):
        raise ValueError("Unexpected or repeated supply-use form fields")

    raw_id = str(form["supply_id"]).strip()
    raw_ref = str(form["reference"]).strip()
    raw_amount = str(form["amount"]).strip()
    if not re.fullmatch(r"[1-9]\d{0,9}", raw_id):
        raise ValueError("Invalid supply selection")
    if not re.fullmatch(r"(dose|reconstitution):[1-9]\d{0,9}", raw_ref):
        raise ValueError("Invalid use reference")
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,4})?", raw_amount):
        raise ValueError("Invalid use amount")
    reference_type, reference_id = raw_ref.split(":", 1)
    return validate_use439({
        "supply_id": int(raw_id),
        "reference_type": reference_type,
        "reference_id": int(reference_id),
        "amount": float(raw_amount),
        "notes": str(form["notes"]).strip(),
        "submission_token": str(form["submission_token"]).strip(),
    })


def _marker(session, uid):
    rows = [tuple(row) for row in session.connection().exec_driver_sql("""
        SELECT user_id,status,schema_version FROM tracker_staged_workspace426
    """).fetchall()]
    if rows != [(uid, "inactive", 426)]:
        raise RuntimeError("Private supply-use workspace mismatch")


def _result(uid, status, **extra):
    return dict(
        mode="private-supply-use439", user_id=uid, status=status,
        login_enabled=False, http_listener_started=False, **extra,
    )


def private_options439(uid, private):
    from sqlalchemy import select
    from .models import (
        Supply, SupplyUsage, DoseLog, PreparationEvent, PreparationSupply, Vial,
    )
    Local = _verified_storage(uid, private)
    with Local() as session:
        _marker(session, uid)
        supplies = list(session.scalars(
            select(Supply).where(Supply.remaining_qty > 0)
            .order_by(Supply.id.desc()).limit(150)))
        stock = [
            dict(id=s.id, name=s.name, kind=s.kind,
                 remaining=float(s.remaining_qty),
                 unit="mL" if s.kind == "bac_water" else "count")
            for s in supplies if s.kind in KINDS
        ]
        doses = list(session.scalars(
            select(DoseLog).where(DoseLog.kind == "dose")
            .order_by(DoseLog.id.desc()).limit(60)))
        events = list(session.scalars(
            select(PreparationEvent)
            .where(PreparationEvent.kind == "reconstitution")
            .order_by(PreparationEvent.id.desc()).limit(60)))
        references = [
            dict(type="dose", id=d.id,
                 label=(f"Dose #{d.id}: {d.vial.compound.name}")[:200])
            for d in doses
        ]
        for e in events:
            vial = session.get(Vial, e.vial_id)
            if vial is not None:
                references.append(dict(
                    type="reconstitution", id=e.id,
                    label=(f"Reconstitution #{e.id}: "
                           + vial.compound.name)[:200],
                ))
        usages = list(session.scalars(
            select(SupplyUsage).order_by(SupplyUsage.id.desc()).limit(40)))
        history = []
        for use in usages:
            supply = session.get(Supply, use.supply_id)
            if supply is None:
                continue
            event_id = session.scalar(
                select(PreparationSupply.event_id)
                .where(PreparationSupply.usage_id == use.id).limit(1))
            ref = (
                f"Dose #{use.dose_id}" if use.dose_id is not None
                else f"Reconstitution #{event_id}" if event_id is not None
                else "Unlinked"
            )
            history.append(dict(
                id=use.id, supply=supply.name, amount=float(use.amount),
                unit="mL" if supply.kind == "bac_water" else "count",
                reference=ref,
            ))
    return _result(
        uid, "options", supplies=stock,
        references=references, history=history,
    )


def _reject(uid, message):
    return _result(
        uid, "rejected", written=False, error=message[:180],
    )


def private_use439(uid, private, payload):
    if os.getenv("TRACKER_WORKER_SUPPLY_USE439") != "1":
        raise PermissionError("Private supply use disabled")
    payload = validate_use439(payload)
    Local = _verified_storage(uid, private)

    from sqlalchemy import func, select
    from sqlalchemy.exc import OperationalError
    from . import idempotency
    from .models import (
        Supply, SupplyUsage, DoseLog, PreparationEvent,
        PreparationSupply, Vial, ChangeAudit,
    )

    with Local() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private supply inventory busy") from exc
        _marker(session, uid)
        state, digest = idempotency.check(
            session, payload["submission_token"], OPERATION,
            {k: v for k, v in payload.items() if k != "submission_token"},
        )
        if state != "new":
            session.rollback()
            return _result(uid, "duplicate", written=False)

        supply = session.get(Supply, payload["supply_id"])
        if supply is None or supply.kind not in KINDS:
            session.rollback()
            return _reject(uid, "Supply unavailable")
        amount = payload["amount"]
        if supply.kind in COUNT_KINDS and not amount.is_integer():
            session.rollback()
            return _reject(uid, "Counted supplies require whole units")
        if (not math.isfinite(supply.remaining_qty)
            or supply.remaining_qty <= 0
            or amount > supply.remaining_qty + 1e-9):
            session.rollback()
            return _reject(uid, "Insufficient supply inventory")

        reference_id = payload["reference_id"]
        reference_type = payload["reference_type"]
        if reference_type == "dose":
            if supply.kind == "bac_water":
                session.rollback()
                return _reject(uid, "BAC water can only link to reconstitution")
            dose = session.get(DoseLog, reference_id)
            if dose is None or dose.kind != "dose":
                session.rollback()
                return _reject(uid, "Dose unavailable")
            previous = session.scalar(
                select(SupplyUsage.id).where(
                    SupplyUsage.supply_id == supply.id,
                    SupplyUsage.dose_id == dose.id,
                ).limit(1))
            if previous is not None:
                session.rollback()
                return _reject(uid, "Supply already linked to this dose")
            use = SupplyUsage(
                supply_id=supply.id, vial_id=dose.vial_id,
                dose_id=dose.id, amount=amount,
            )
            session.add(use)
        else:
            event = session.get(PreparationEvent, reference_id)
            if event is None or event.kind != "reconstitution":
                session.rollback()
                return _reject(uid, "Reconstitution unavailable")
            previous = session.scalar(
                select(SupplyUsage.id)
                .join(PreparationSupply,
                      PreparationSupply.usage_id == SupplyUsage.id)
                .where(
                    PreparationSupply.event_id == event.id,
                    SupplyUsage.supply_id == supply.id,
                ).limit(1))
            if previous is not None:
                session.rollback()
                return _reject(uid, "Supply already linked to this preparation")
            if supply.kind == "bac_water":
                vial = session.get(Vial, event.vial_id)
                already = session.scalar(
                    select(func.sum(SupplyUsage.amount))
                    .join(PreparationSupply,
                          PreparationSupply.usage_id == SupplyUsage.id)
                    .join(Supply, Supply.id == SupplyUsage.supply_id)
                    .where(
                        PreparationSupply.event_id == event.id,
                        Supply.kind == "bac_water",
                    )
                ) or 0.0
                if (vial is None or vial.volume_ml is None
                    or not math.isfinite(vial.volume_ml)
                    or amount + already > vial.volume_ml + 1e-9):
                    session.rollback()
                    return _reject(uid, "BAC water exceeds recorded volume")
            use = SupplyUsage(
                supply_id=supply.id, vial_id=event.vial_id, amount=amount,
            )
            session.add(use)
            session.flush()
            session.add(PreparationSupply(event_id=event.id, usage_id=use.id))

        before = float(supply.remaining_qty)
        supply.remaining_qty = max(0.0, before - amount)
        session.flush()
        use_id = use.id
        session.add(ChangeAudit(
            entity_type="supply", entity_id=supply.id,
            action="secondary_supply_use439",
            before_json=json.dumps(dict(remaining=before), sort_keys=True),
            after_json=json.dumps(dict(
                remaining=supply.remaining_qty, deducted=amount,
                reference_type=reference_type, reference_id=reference_id,
                reason=payload["notes"],
            ), sort_keys=True),
        ))
        idempotency.record(
            session, payload["submission_token"], OPERATION, digest,
        )
        session.commit()
        return _result(uid, "created", written=True, id=use_id)


def request_use439(user_id, action, payload=None, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if (config.instance_label() not in ("DEV", "PROD")
        or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1"):
        raise PermissionError("Secondary supply preview disabled")
    if type(action) is not str or action not in ("options", "use"):
        raise ValueError("Unsupported supply-use action")
    if action == "options" and payload is not None:
        raise ValueError("Options take no payload")
    if action == "use":
        if os.getenv("TRACKER_SECONDARY_SUPPLY_USE439") != "1":
            raise PermissionError("Private supply use disabled")
        payload = validate_use439(payload)
    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)
    if action == "use":
        env["TRACKER_WORKER_SUPPLY_USE439"] = "1"
    request = {"action": action}
    if payload is not None:
        request["payload"] = payload
    result = subprocess.run(
        [sys.executable, "-m", "app.worker_supply_use439"],
        input=json.dumps(request, separators=(",", ":"), allow_nan=False),
        cwd=SOURCE_ROOT, env=env, text=True, capture_output=True,
        timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Private supply-use worker failed ({result.returncode}): "
            + result.stderr[-1000:])
    try:
        answer = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid supply-use response") from exc
    if (type(answer) is not dict
        or answer.get("mode") != "private-supply-use439"
        or answer.get("user_id") != uid
        or answer.get("login_enabled") is not False
        or answer.get("http_listener_started") is not False):
        raise RuntimeError("Private supply-use identity mismatch")
    if action == "options":
        if (answer.get("status") != "options"
            or type(answer.get("supplies")) is not list
            or type(answer.get("references")) is not list
            or type(answer.get("history")) is not list
            or len(answer["supplies"]) > 150
            or len(answer["references"]) > 120
            or len(answer["history"]) > 40):
            raise RuntimeError("Invalid supply-use options")
        for row in answer["supplies"]:
            if (type(row) is not dict
                or set(row) != {"id","name","kind","remaining","unit"}
                or type(row["id"]) is not int or type(row["name"]) is not str
                or row["kind"] not in KINDS
                or row["unit"] not in ("mL","count")
                or type(row["remaining"]) not in (int,float)
                or not math.isfinite(row["remaining"])):
                raise RuntimeError("Invalid supply-use item")
        for row in answer["references"]:
            if (type(row) is not dict
                or set(row) != {"type","id","label"}
                or row["type"] not in ("dose","reconstitution")
                or type(row["id"]) is not int or type(row["label"]) is not str):
                raise RuntimeError("Invalid supply-use reference")
        for row in answer["history"]:
            if (type(row) is not dict
                or set(row) != {"id","supply","amount","unit","reference"}
                or type(row["id"]) is not int
                or any(type(row[k]) is not str
                       for k in ("supply","unit","reference"))
                or type(row["amount"]) not in (int,float)
                or not math.isfinite(row["amount"])):
                raise RuntimeError("Invalid supply-use history")
    elif (answer.get("status") not in ("created","duplicate","rejected")
          or type(answer.get("written")) is not bool
          or answer["written"] != (answer["status"] == "created")
          or (answer["status"] == "created"
              and type(answer.get("id")) is not int)
          or (answer["status"] == "rejected"
              and (type(answer.get("error")) is not str
                   or len(answer["error"]) > 180))):
        raise RuntimeError("Invalid supply-use result")
    return answer


def main():
    uid, private = validate_environment()
    action, payload = parse_request439(sys.stdin.buffer.read(MAX_BYTES + 1))
    report = (private_options439(uid, private) if action == "options"
              else private_use439(uid, private, payload))
    print(json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
