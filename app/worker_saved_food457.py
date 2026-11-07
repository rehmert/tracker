"""Release 457: isolated saved-food listing and quick logging.

The worker accepts no user ID, path, SQL or database name.
The current authenticated user's workspace is selected by
the parent and independently verified by the child.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from urllib.parse import quote

from .worker_probe428 import validate_environment
from .worker_read429 import private_overview429
from .worker_food452 import validate_day452

MAX_BYTES = 512
MAX_ITEMS = 100
OPERATION = "secondary_saved_food457"


def unique_object457(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("Duplicate request field")
        output[key] = value
    return output


def validate_reuse457(payload):
    expected = {
        "product_id", "day", "meal",
        "servings", "submission_token",
    }
    if type(payload) is not dict or set(payload) != expected:
        raise ValueError("Unexpected quick food fields")

    product_id = payload["product_id"]
    if (
        type(product_id) is not int
        or not 1 <= product_id <= 2147483647
    ):
        raise ValueError("Invalid saved food ID")

    day = validate_day452(payload["day"])
    meal = payload["meal"]
    if meal not in (
        "Breakfast", "Lunch", "Dinner", "Snack"
    ):
        raise ValueError("Invalid meal")

    raw = payload["servings"]
    if type(raw) is not str or not re.fullmatch(
        r"\d{1,3}(?:\.\d{1,3})?", raw
    ):
        raise ValueError("Invalid servings")

    servings = float(raw)
    if not 0 < servings <= 100:
        raise ValueError("Servings out of range")

    token = payload["submission_token"]
    if type(token) is not str:
        raise ValueError("Invalid submission token")

    try:
        parsed = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid submission token") from None

    if parsed.version != 4 or str(parsed) != token:
        raise ValueError("Invalid submission token")

    return {
        "product_id": product_id,
        "day": day,
        "meal": meal,
        "servings": servings,
        "submission_token": token,
    }


def parse_request457(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid request size")

    try:
        request = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=unique_object457,
        )
    except (ValueError, UnicodeError):
        raise ValueError("Invalid quick food request") from None

    if type(request) is not dict:
        raise ValueError("Invalid quick food request")

    if set(request) == {"action"} and request["action"] == "list":
        return "list", None

    if (
        set(request) == {"action", "payload"}
        and request["action"] == "reuse"
    ):
        return "reuse", validate_reuse457(request["payload"])

    raise ValueError("Unsupported quick food request")


def form_reuse457(form):
    expected = {
        "csrf_token", "product_id", "day",
        "meal", "servings", "submission_token",
    }

    if set(form) != expected or any(
        len(form.getlist(key)) != 1 for key in expected
    ):
        raise ValueError("Unexpected quick food form fields")

    raw_id = str(form["product_id"]).strip()
    if not re.fullmatch(r"[1-9]\d{0,9}", raw_id):
        raise ValueError("Invalid saved food ID")

    data = {
        "product_id": int(raw_id),
        "day": str(form["day"]).strip(),
        "meal": str(form["meal"]).strip(),
        "servings": str(form["servings"]).strip(),
        "submission_token":
            str(form["submission_token"]).strip(),
    }
    return validate_reuse457(data)


def _database457(uid, private, writable):
    private_overview429(uid, private)
    path = private / "tracker.db"
    uri = (
        "file:" + quote(str(path), safe="/")
        + ("?mode=rw" if writable else "?mode=ro")
    )
    db = sqlite3.connect(
        uri, uri=True, timeout=5, isolation_level=None
    )
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    if not writable:
        db.execute("PRAGMA query_only=ON")
    return db


def _identity457(db, uid):
    marker = db.execute("""
        SELECT user_id,status,schema_version
        FROM tracker_staged_workspace426
    """).fetchall()
    if marker != [(uid, "inactive", 426)]:
        raise RuntimeError("Private food identity mismatch")


def private_list457(uid, private):
    with _database457(uid, private, False) as db:
        _identity457(db, uid)

        rows = db.execute("""
            SELECT p.id, substr(p.name,1,160),
                   substr(p.serving_description,1,80)
            FROM tracker_food_products p
            JOIN (
                SELECT product_id,MAX(id) newest
                FROM tracker_food_entries
                GROUP BY product_id
            ) recent ON recent.product_id=p.id
            ORDER BY recent.newest DESC
            LIMIT ?
        """, (MAX_ITEMS,)).fetchall()

    return {
        "mode": "private-saved-food457",
        "user_id": uid,
        "status": "list",
        "items": [
            {"id": item_id, "name": name, "serving": serving}
            for item_id, name, serving in rows
        ],
    }


def private_reuse457(uid, private, payload):
    if os.getenv("TRACKER_WORKER_SAVED_FOOD_WRITE457") != "1":
        raise PermissionError("Saved food writes disabled")

    # Validate a normalized payload using the strict wire contract.
    payload = validate_reuse457({
        **payload,
        "servings": str(payload["servings"]),
    })

    db = _database457(uid, private, True)

    try:
        db.execute("BEGIN IMMEDIATE")
        _identity457(db, uid)

        token = payload["submission_token"]

        existing = db.execute("""
            SELECT token FROM inventory_submissions
            WHERE token=?
        """, (token,)).fetchone()

        if existing:
            db.rollback()
            return {
                "mode": "private-saved-food457",
                "user_id": uid,
                "status": "duplicate",
                "written": False,
            }

        product = db.execute("""
            SELECT id FROM tracker_food_products
            WHERE id=?
        """, (payload["product_id"],)).fetchone()

        if product is None:
            raise ValueError("Saved food not found")

        db.execute("""
            INSERT INTO tracker_food_entries
                (product_id,eaten_on,meal,servings)
            VALUES (?,?,?,?)
        """, (
            payload["product_id"],
            payload["day"],
            payload["meal"],
            payload["servings"],
        ))

        fingerprint = json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key != "submission_token"
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        digest = hashlib.sha256(
            fingerprint.encode("utf-8")
        ).hexdigest()

        db.execute("""
            INSERT INTO inventory_submissions
                (token,operation,payload_hash)
            VALUES (?,?,?)
        """, (token, OPERATION, digest))

        db.commit()

    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "mode": "private-saved-food457",
        "user_id": uid,
        "status": "created",
        "written": True,
    }


def request_saved457(uid, action, payload=None, data_root=None):
    from . import config
    from .user_accounts427 import secondary_id
    from .worker_scope428 import (
        SOURCE_ROOT, worker_environment428
    )

    if (
        config.instance_label() != "DEV"
        or os.getenv("TRACKER_SECONDARY_FOOD_WRITES456", "0") != "1"
    ):
        raise PermissionError("Private food logging disabled")

    uid = secondary_id(uid)

    if action == "list":
        if payload is not None:
            raise ValueError("List accepts no payload")
        message = {"action": "list"}
    elif action == "reuse":
        validated = validate_reuse457({
            **payload,
            "servings": str(payload["servings"]),
        })
        message = {
            "action": "reuse",
            "payload": {
                **validated,
                "servings": str(validated["servings"]),
            },
        }
    else:
        raise ValueError("Unsupported saved food action")

    environment = worker_environment428(uid, data_root)

    if action == "reuse":
        environment["TRACKER_WORKER_SAVED_FOOD_WRITE457"] = "1"

    encoded = json.dumps(
        message, separators=(",", ":"), allow_nan=False
    )
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError("Quick food request too large")

    process = subprocess.run(
        [sys.executable, "-m", "app.worker_saved_food457"],
        input=encoded,
        cwd=SOURCE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    if process.returncode:
        raise RuntimeError("Private saved food worker unavailable")

    try:
        response = json.loads(process.stdout)
    except (ValueError, TypeError):
        raise RuntimeError("Invalid saved food response") from None

    if (
        type(response) is not dict
        or response.get("mode") != "private-saved-food457"
        or type(response.get("user_id")) is not int
        or response["user_id"] != uid
    ):
        raise RuntimeError("Saved food identity mismatch")

    if action == "list":
        if (
            set(response) != {
                "mode", "user_id", "status", "items"
            }
            or response["status"] != "list"
            or type(response["items"]) is not list
            or len(response["items"]) > MAX_ITEMS
        ):
            raise RuntimeError("Invalid saved food list")

        for item in response["items"]:
            if (
                type(item) is not dict
                or set(item) != {"id", "name", "serving"}
                or type(item["id"]) is not int
                or item["id"] <= 0
                or type(item["name"]) is not str
                or len(item["name"]) > 160
                or type(item["serving"]) is not str
                or len(item["serving"]) > 80
            ):
                raise RuntimeError("Invalid saved food item")
    else:
        if (
            set(response) != {
                "mode", "user_id", "status", "written"
            }
            or response["status"] not in (
                "created", "duplicate"
            )
            or type(response["written"]) is not bool
            or response["written"] != (
                response["status"] == "created"
            )
        ):
            raise RuntimeError("Invalid quick food write response")

    return response


def main():
    uid, private = validate_environment()
    action, payload = parse_request457(
        sys.stdin.buffer.read(MAX_BYTES + 1)
    )

    if action == "list":
        result = private_list457(uid, private)
    else:
        result = private_reuse457(uid, private, payload)

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
