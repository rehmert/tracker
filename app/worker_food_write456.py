"""DEV-gated secondary food and water writes.

Only the parent-selected private workspace is opened.
No user ID, filesystem path, database URL, or SQL is accepted
from a browser or worker request.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid

from .worker_probe428 import validate_environment
from .worker_dose_write434 import _verified_storage
from .worker_food452 import validate_day452

MAX_BYTES = 4096
NUTRIENTS = (
    "energy", "proteins", "carbohydrates", "fat", "fiber"
)
MEALS = ("Breakfast", "Lunch", "Dinner", "Snack")
ACTIONS = ("water", "food")
OPERATION = "secondary_food_write456"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate request field")
        result[key] = value
    return result


def _quantity(raw, maximum):
    if type(raw) is not str or not re.fullmatch(
        r"\d{1,6}(?:\.\d{1,3})?", raw
    ):
        raise ValueError("Invalid numeric quantity")
    number = float(raw)
    if not 0 < number <= maximum:
        raise ValueError("Quantity out of range")
    return number


def validate_payload456(action, data):
    if action not in ACTIONS or type(data) is not dict:
        raise ValueError("Unsupported private food operation")

    common = {"day", "submission_token"}
    expected = (
        common | {"ounces"} if action == "water"
        else common | {
            "name", "meal", "servings",
            *NUTRIENTS,
        }
    )

    if set(data) != expected:
        raise ValueError("Unexpected private food fields")

    day = validate_day452(data["day"])
    token = data["submission_token"]
    if type(token) is not str:
        raise ValueError("Invalid submission token")
    try:
        value = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid submission token") from None
    if value.version != 4 or str(value) != token:
        raise ValueError("Invalid submission token")

    result = {
        "day": day,
        "submission_token": token,
    }

    if action == "water":
        result["ounces"] = _quantity(data["ounces"], 256)
        return result

    name = data["name"]
    meal = data["meal"]
    if (
        type(name) is not str
        or not 1 <= len(name.strip()) <= 160
        or any(ord(ch) < 32 for ch in name)
    ):
        raise ValueError("Invalid food name")

    if type(meal) is not str or meal not in MEALS:
        raise ValueError("Invalid meal")

    result.update(
        name=name.strip(),
        meal=meal,
        servings=_quantity(data["servings"], 100),
    )

    nutrients = {}
    for key in NUTRIENTS:
        raw = data[key]
        if type(raw) is not str:
            raise ValueError("Invalid nutrient field")
        if raw == "":
            nutrients[key] = None
        else:
            if not re.fullmatch(
                r"\d{1,6}(?:\.\d{1,3})?", raw
            ):
                raise ValueError("Invalid nutrient amount")
            amount = float(raw)
            if not 0 <= amount <= 100000:
                raise ValueError("Nutrient outside supported range")
            nutrients[key] = amount

    if all(value is None for value in nutrients.values()):
        raise ValueError("Enter at least one known nutrient")

    result["nutrients"] = nutrients
    return result


def parse_request456(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid private request length")

    try:
        message = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
        )
    except (UnicodeError, ValueError):
        raise ValueError("Invalid private request") from None

    if (
        type(message) is not dict
        or set(message) != {"action", "payload"}
    ):
        raise ValueError("Unexpected private request fields")

    action = message["action"]
    return action, validate_payload456(
        action, message["payload"]
    )


def form_payload456(action, form):
    if action not in ACTIONS:
        raise ValueError("Unsupported form action")

    expected = (
        {"day", "submission_token", "ounces", "csrf_token"}
        if action == "water"
        else {
            "day", "submission_token", "csrf_token",
            "name", "meal", "servings", *NUTRIENTS,
        }
    )
    if set(form) != expected or any(
        len(form.getlist(key)) != 1 for key in expected
    ):
        raise ValueError("Unexpected or repeated form fields")

    data = {
        key: str(form[key]).strip()
        for key in expected - {"csrf_token"}
    }
    return validate_payload456(action, data)


def private_write456(uid, private, action, payload):
    if os.getenv("TRACKER_WORKER_FOOD_WRITE456") != "1":
        raise PermissionError("Private food writes disabled")

    payload = validate_payload456(action, {
        **{
            key: str(value) if key not in (
                "nutrients", "submission_token", "day",
                "name", "meal"
            ) else value
            for key, value in payload.items()
            if key != "nutrients"
        },
        **(
            {
                key: (
                    "" if payload["nutrients"][key] is None
                    else str(payload["nutrients"][key])
                )
                for key in NUTRIENTS
            }
            if action == "food" else {}
        ),
    })

    SessionLocal = _verified_storage(uid, private)
    # Resolve the connection only from the verified private engine.
    with SessionLocal() as session:
        conn = session.connection()
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        marker = conn.exec_driver_sql("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
        if [tuple(x) for x in marker] != [
            (uid, "inactive", 426)
        ]:
            raise RuntimeError("Private workspace identity changed")

        token = payload["submission_token"]
        from . import idempotency
        fingerprint = {
            "action": action,
            **{
                k: v for k, v in payload.items()
                if k != "submission_token"
            },
        }
        operation = OPERATION + "_" + action
        state, digest = idempotency.check(
            session, token, operation, fingerprint
        )
        if state != "new":
            session.rollback()
            return {
                "mode": "private-food-write456",
                "user_id": uid,
                "status": "duplicate",
                "written": False,
            }

        if action == "water":
            result = conn.exec_driver_sql("""
                INSERT INTO tracker_water_entries
                    (logged_on,ounces) VALUES (?,?)
            """, (payload["day"], payload["ounces"]))
        else:
            result = conn.exec_driver_sql("""
                INSERT INTO tracker_food_products
                    (name,serving_description,nutrients,source)
                VALUES (?,?,?,?)
            """, (
                payload["name"], "1 serving",
                json.dumps(payload["nutrients"], sort_keys=True),
                "secondary-manual456",
            ))
            product_id = result.lastrowid
            result = conn.exec_driver_sql("""
                INSERT INTO tracker_food_entries
                    (product_id,eaten_on,meal,servings)
                VALUES (?,?,?,?)
            """, (
                product_id, payload["day"],
                payload["meal"], payload["servings"],
            ))

        idempotency.record(session, token, operation, digest)
        session.commit()

        return {
            "mode": "private-food-write456",
            "user_id": uid,
            "status": "created",
            "written": True,
        }


def request_write456(uid, action, payload, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import (
        SOURCE_ROOT, worker_environment428
    )

    if (
        config.instance_label() != "DEV"
        or os.getenv(
            "TRACKER_SECONDARY_FOOD_WRITES456", "0"
        ) != "1"
    ):
        raise PermissionError("Secondary food logging disabled")

    uid = secondary_id(uid)
    if action not in ACTIONS:
        raise ValueError("Unsupported action")

    # Form validation is repeated inside the child.
    environment = worker_environment428(uid, data_root)
    environment["TRACKER_WORKER_FOOD_WRITE456"] = "1"

    message = {
        "action": action,
        "payload": {
            **{
                k: (
                    str(v) if k in ("ounces", "servings") else v
                )
                for k, v in payload.items()
                if k != "nutrients"
            },
            **(
                {
                    key: (
                        "" if payload["nutrients"][key] is None
                        else str(payload["nutrients"][key])
                    )
                    for key in NUTRIENTS
                }
                if action == "food" else {}
            ),
        },
    }
    encoded = json.dumps(
        message, separators=(",", ":"), allow_nan=False
    )
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError("Private request too large")

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_food_write456"],
        input=encoded,
        cwd=SOURCE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Private food writer unavailable")

    try:
        response = json.loads(result.stdout)
    except (TypeError, ValueError):
        raise RuntimeError("Invalid private write response") from None

    if (
        type(response) is not dict
        or set(response) != {
            "mode", "user_id", "status", "written"
        }
        or response["mode"] != "private-food-write456"
        or type(response["user_id"]) is not int
        or response["user_id"] != uid
        or response["status"] not in ("created", "duplicate")
        or type(response["written"]) is not bool
        or response["written"] != (
            response["status"] == "created"
        )
    ):
        raise RuntimeError("Private food write identity mismatch")

    return response


def main():
    uid, private = validate_environment()
    action, payload = parse_request456(
        sys.stdin.buffer.read(MAX_BYTES + 1)
    )
    print(json.dumps(
        private_write456(uid, private, action, payload),
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
