"""Release 434: DEV-only, fail-closed, private single-vial dose creation.

The isolated child selects its SQLite database from its verified environment,
never from a browser payload. Use the existing inventory/units/idempotency
implementation under a SQLite write reservation.
"""

import json
import math
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta

MAX_BYTES = 4096
OPERATION = "secondary_dose_create434"
FIELDS = frozenset({
    "vial_id", "taken_at", "amount", "unit", "site", "notes", "submission_token",
})
UNITS = frozenset(("mcg", "mg", "g", "IU", "mL", "uL"))
TIME_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\Z")


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate request field")
        result[key] = value
    return result


def validate_dose434(payload):
    if type(payload) is not dict or set(payload) != FIELDS:
        raise ValueError("Unexpected dose fields")

    vid = payload["vial_id"]
    if type(vid) is not int or not 1 <= vid <= 2147483647:
        raise ValueError("Choose a valid vial")

    value = payload["amount"]
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 < value <= 1000000
    ):
        raise ValueError("Amount must be finite and above zero")

    unit = payload["unit"]
    if type(unit) is not str or unit not in UNITS:
        raise ValueError("Unsupported dose unit")

    raw_when = payload["taken_at"]
    if type(raw_when) is not str or not TIME_FORMAT.fullmatch(raw_when):
        raise ValueError("Invalid dose timestamp")
    try:
        when = datetime.fromisoformat(raw_when)
    except ValueError as exc:
        raise ValueError("Invalid dose timestamp") from exc
    if when < datetime(2000, 1, 1) or when > datetime.now() + timedelta(days=1):
        raise ValueError("Dose timestamp outside supported range")

    from .routers.doses import INJECTION_SITES
    site = payload["site"]
    if type(site) is not str or site not in ("", *INJECTION_SITES):
        raise ValueError("Unknown injection site")
    notes = payload["notes"]
    if (
        type(notes) is not str or len(notes) > 2000
        or any(ord(char) < 32 and char not in "\n\t" for char in notes)
    ):
        raise ValueError("Invalid dose notes")

    token = payload["submission_token"]
    if type(token) is not str:
        raise ValueError("Invalid dose submission token")
    try:
        uid = uuid.UUID(token)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid dose submission token") from exc
    if uid.version != 4 or str(uid) != token:
        raise ValueError("Invalid dose submission token")
    return payload


def parse_request434(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid private dose request size")
    try:
        message = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_strict_object,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private dose request JSON") from exc
    if type(message) is not dict or type(message.get("action")) is not str:
        raise ValueError("Invalid private dose request")
    if message["action"] == "options" and set(message) == {"action"}:
        return "options", None
    if message["action"] == "create_dose" and set(message) == {"action", "payload"}:
        return "create_dose", validate_dose434(message["payload"])
    raise ValueError("Unsupported private dose operation")


def form_payload434(form):
    """Reject duplicate/extra form fields before parsing values."""
    names = {
        "csrf_token", "submission_token", "vial_id", "taken_at",
        "amount", "unit", "site", "notes",
    }
    if set(form) != names or any(len(form.getlist(key)) != 1 for key in names):
        raise ValueError("Unexpected dose form fields")

    raw_id = str(form["vial_id"]).strip()
    raw_amount = str(form["amount"]).strip()
    if not re.fullmatch(r"[1-9]\d{0,9}", raw_id):
        raise ValueError("Choose a valid vial")
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,6})?", raw_amount):
        raise ValueError("Invalid dose amount")

    payload = {
        "vial_id": int(raw_id),
        "taken_at": str(form["taken_at"]).strip(),
        "amount": float(raw_amount),
        "unit": str(form["unit"]).strip(),
        "site": str(form["site"]).strip(),
        "notes": str(form["notes"]).strip(),
        "submission_token": str(form["submission_token"]).strip(),
    }
    return validate_dose434(payload)


def _verified_storage(uid, private):
    from .worker_read429 import private_overview429
    private_overview429(uid, private)

    from . import config, db
    if (
        config.DATA_DIR != private
        or config.DB_PATH != private / "tracker.db"
        or db.engine.url.get_backend_name() != "sqlite"
        or not db.engine.url.database
        or os.path.abspath(db.engine.url.database) != str(private / "tracker.db")
    ):
        raise RuntimeError("Private worker storage mismatch")
    return db.SessionLocal


def private_options434(uid, private):
    from sqlalchemy import select
    from .models import Vial
    from .services import vial_views

    SessionLocal = _verified_storage(uid, private)
    with SessionLocal() as session:
        vials = list(session.scalars(
            select(Vial)
            .where(Vial.status.in_(("sealed", "in_use")))
            .order_by(Vial.id.desc()).limit(200)
        ))
        views = vial_views(session, vials)
        items = []
        for vial in vials:
            view = views[vial.id]
            if not math.isfinite(view.remaining_base) or view.remaining_base <= 0:
                continue
            items.append({
                "id": vial.id,
                "label": (
                    vial.compound.name + " · " +
                    (vial.label or "Vial #" + str(vial.id))
                )[:240],
                "remaining_base": round(view.remaining_base, 6),
                "base_unit": "IU" if view.dim == "iu" else "mcg",
            })
    return {
        "mode": "offline-dose434",
        "status": "options",
        "user_id": uid,
        "items": items,
        "http_listener_started": False,
        "login_enabled": False,
    }


def private_create_dose434(uid, private, payload):
    if os.getenv("TRACKER_WORKER_DOSE_WRITE434") != "1":
        raise PermissionError("Private dose writes are disabled")

    validate_dose434(payload)
    SessionLocal = _verified_storage(uid, private)

    from . import idempotency, services, units
    from .models import Vial, DoseLog
    from sqlalchemy.exc import OperationalError

    with SessionLocal() as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.rollback()
            raise RuntimeError("Private inventory is busy") from exc

        # Inside the write lock, recheck identity and submit token.
        marker = [
            tuple(row) for row in session.connection().exec_driver_sql("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
        ]
        if marker != [(uid, "inactive", 426)]:
            session.rollback()
            raise RuntimeError("Private workspace identity changed")

        state, digest = idempotency.check(
            session, payload["submission_token"], OPERATION, {
                key: value for key, value in payload.items()
                if key != "submission_token"
            },
        )
        if state != "new":
            session.rollback()
            return {
                "mode": "offline-dose434", "status": "duplicate",
                "user_id": uid, "written": False,
                "login_enabled": False, "http_listener_started": False,
            }

        vial = session.get(Vial, payload["vial_id"])
        if vial is None or vial.status not in ("sealed", "in_use"):
            session.rollback()
            return {
                "mode": "offline-dose434", "status": "rejected",
                "user_id": uid, "written": False,
                "error": "Vial is unavailable",
                "login_enabled": False, "http_listener_started": False,
            }

        view = services.vial_views(session, [vial])[vial.id]
        try:
            base = units.amount_to_vial_base(
                payload["amount"], payload["unit"],
                view.dim, view.conc_per_ml,
            )
            if (
                not math.isfinite(base) or base <= 0
                or not math.isfinite(view.remaining_base)
                or view.remaining_base <= 0
                or base > view.remaining_base + 1e-7
            ):
                raise ValueError("Amount exceeds remaining vial contents")
            unit = units.parse_unit(payload["unit"]).name
        except ValueError as exc:
            session.rollback()
            return {
                "mode": "offline-dose434", "status": "rejected",
                "user_id": uid, "written": False, "error": str(exc)[:180],
                "login_enabled": False, "http_listener_started": False,
            }

        dose = DoseLog(
            vial_id=vial.id,
            taken_at=datetime.fromisoformat(payload["taken_at"]),
            entered_value=payload["amount"],
            entered_unit=unit,
            amount_base=base,
            kind="dose",
            site=payload["site"],
            notes=payload["notes"],
        )
        session.add(dose)
        if vial.status == "sealed":
            vial.status = "in_use"
        idempotency.record(
            session, payload["submission_token"], OPERATION, digest,
        )
        session.flush()
        dose_id = dose.id
        session.commit()
        return {
            "mode": "offline-dose434", "status": "created",
            "user_id": uid, "written": True, "id": dose_id,
            "login_enabled": False, "http_listener_started": False,
        }


def request_dose434(user_id, action, payload=None, data_root=None):
    """Parent API: fixed operation, verified account, isolated child."""
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    if (
        config.instance_label() not in ("DEV", "PROD")
        or os.getenv("TRACKER_SECONDARY_PREVIEW430") != "1"
        or os.getenv("TRACKER_SECONDARY_DOSE_WRITES434") != "1"
    ):
        raise PermissionError("Secondary dose logging is disabled")
    if action not in ("options", "create_dose"):
        raise ValueError("Unsupported dose operation")

    uid = secondary_id(user_id)
    body = {"action": action}
    if action == "create_dose":
        body["payload"] = validate_dose434(payload)
    elif payload is not None:
        raise ValueError("Options cannot include a payload")

    env = worker_environment428(uid, data_root)
    if action == "create_dose":
        env["TRACKER_WORKER_DOSE_WRITE434"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_dose_write434"],
        input=json.dumps(body, separators=(",", ":"), allow_nan=False),
        cwd=SOURCE_ROOT, env=env,
        capture_output=True, text=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Private dose worker failed (exit "
            + str(result.returncode) + "): " + result.stderr[-1000:]
        )
    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Private dose worker returned invalid JSON") from exc

    expected = "options" if action == "options" else None
    if (
        type(report) is not dict
        or report.get("mode") != "offline-dose434"
        or report.get("user_id") != uid
        or report.get("login_enabled") is not False
        or report.get("http_listener_started") is not False
        or (expected is not None and report.get("status") != expected)
    ):
        raise RuntimeError("Private dose worker identity mismatch")

    if action == "options":
        items = report.get("items")
        if (
            type(items) is not list or len(items) > 200 or
            any(
                type(item) is not dict
                or set(item) != {"id", "label", "remaining_base", "base_unit"}
                or type(item["id"]) is not int
                or type(item["label"]) is not str
                or type(item["remaining_base"]) not in (float, int)
                or item["base_unit"] not in ("IU", "mcg")
                for item in items
            )
        ):
            raise RuntimeError("Private dose options malformed")
    else:
        if (
            report.get("status") not in ("created", "rejected", "duplicate")
            or type(report.get("written")) is not bool
            or report["written"] != (report["status"] == "created")
            or (report["status"] == "created"
                and type(report.get("id")) is not int)
            or (report["status"] == "rejected"
                and (type(report.get("error")) is not str
                     or len(report["error"]) > 180))
        ):
            raise RuntimeError("Private dose write response malformed")
    return report


def main():
    from .worker_probe428 import validate_environment
    uid, private = validate_environment()
    action, payload = parse_request434(sys.stdin.buffer.read(MAX_BYTES + 1))
    report = (
        private_options434(uid, private)
        if action == "options"
        else private_create_dose434(uid, private, payload)
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
