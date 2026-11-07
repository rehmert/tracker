"""Release 452: read-only, account-isolated food and water daily history.

The parent chooses a staged user from an authenticated secondary session.
A separate isolated subprocess opens only that user's SQLite database in
read-only mode. The child accepts only a single allowlisted day, never SQL,
paths, user IDs or arbitrary queries. No writes or HTTP listener.
"""
from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from datetime import date
from urllib.parse import quote

from .worker_probe428 import validate_environment
from .worker_read429 import private_overview429

ACTION = "food_day"
MAX_REQUEST = 128
MAX_ROWS = 100
NUTRIENTS = ("energy", "proteins", "carbohydrates", "fat", "fiber")
FIELDS = frozenset(("name", "meal", "servings") + NUTRIENTS)
WATER_TARGET_OZ = 140.0


def validate_day452(day):
    if type(day) is not str or len(day) != 10:
        raise ValueError("Invalid food date")
    try:
        parsed = date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("Invalid food date") from exc
    if parsed.isoformat() != day:
        raise ValueError("Invalid food date")
    return day


def parse_request452(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("Invalid private food request length")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate private food request key")
            result[key] = value
        return result

    try:
        message = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=unique,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private food request") from exc

    if (
        type(message) is not dict
        or set(message) != {"action", "day"}
        or message["action"] != ACTION
    ):
        raise ValueError("Unsupported private food request")

    return validate_day452(message["day"])


def _safe_number452(value):
    # Unreported values must remain unknown rather than becoming zero.
    if value is None or type(value) not in (float, int):
        return None
    if not math.isfinite(value) or value < 0 or value > 100000:
        return None
    return float(value)


def private_food_day452(uid, private, day):
    day = validate_day452(day)
    private_overview429(uid, private)

    uri = "file:" + quote(str(private / "tracker.db"), safe="/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        db.execute("PRAGMA query_only=ON")
        marker = db.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError("Private food workspace identity mismatch")

        rows = db.execute("""
            SELECT substr(p.name,1,160), substr(e.meal,1,40),
                   e.servings, p.nutrients
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.eaten_on=?
            ORDER BY e.id DESC
            LIMIT ?
        """, (day, MAX_ROWS + 1)).fetchall()
        water = db.execute("""
            SELECT COALESCE(SUM(ounces),0)
            FROM tracker_water_entries WHERE logged_on=?
        """, (day,)).fetchone()[0]

    has_more = len(rows) > MAX_ROWS
    entries = []
    totals = {key: 0.0 for key in NUTRIENTS}
    coverage = {key: 0 for key in NUTRIENTS}

    for name, meal, servings, raw in rows[:MAX_ROWS]:
        quantity = _safe_number452(servings)
        if quantity is None or quantity == 0 or quantity > 100:
            raise RuntimeError("Invalid recorded food serving count")
        try:
            values = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Invalid recorded nutrients") from exc
        if type(values) is not dict:
            raise RuntimeError("Invalid nutrient record")
        item = {
            "name": str(name or "")[:160],
            "meal": str(meal or "Snack")[:40],
            "servings": quantity,
        }
        for key in NUTRIENTS:
            per_serving = _safe_number452(values.get(key))
            if per_serving is None:
                item[key] = None
            else:
                amount = round(per_serving * quantity, 2)
                item[key] = amount
                totals[key] += amount
                coverage[key] += 1
        entries.append(item)

    water_value = _safe_number452(water)
    if water_value is None:
        raise RuntimeError("Invalid recorded water total")

    return {
        "mode": "offline-food-day452",
        "user_id": uid,
        "day": day,
        "items": entries,
        "totals": {key: round(value, 2) for key, value in totals.items()},
        "coverage": coverage,
        "water_oz": round(water_value, 2),
        "water_target_oz": WATER_TARGET_OZ,
        "has_more": has_more,
        "login_enabled": False,
        "http_listener_started": False,
    }


def read_food_day452(user_id, day, data_root=None):
    day = validate_day452(day)
    from .user_accounts427 import secondary_id
    from .worker_scope428 import SOURCE_ROOT, worker_environment428

    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_food452"],
        input=json.dumps({"action": ACTION, "day": day}, separators=(",", ":")),
        cwd=SOURCE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Isolated food history unavailable")

    try:
        report = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid private food worker response") from exc

    if (
        type(report) is not dict
        or set(report) != {
            "mode", "user_id", "day", "items", "totals", "coverage",
            "water_oz", "water_target_oz", "has_more",
            "login_enabled", "http_listener_started",
        }
        or report["mode"] != "offline-food-day452"
        or type(report["user_id"]) is not int
        or report["user_id"] != uid
        or report["day"] != day
        or report["login_enabled"] is not False
        or report["http_listener_started"] is not False
        or type(report["has_more"]) is not bool
    ):
        raise RuntimeError("Private food identity contract failed")

    items = report["items"]
    totals = report["totals"]
    coverage = report["coverage"]
    if (
        type(items) is not list
        or len(items) > MAX_ROWS
        or type(totals) is not dict
        or set(totals) != set(NUTRIENTS)
        or type(coverage) is not dict
        or set(coverage) != set(NUTRIENTS)
        or any(
            type(item) is not dict
            or set(item) != FIELDS
            or type(item["name"]) is not str
            or len(item["name"]) > 160
            or type(item["meal"]) is not str
            or len(item["meal"]) > 40
            or _safe_number452(item["servings"]) is None
            or any(
                value is not None and _safe_number452(value) is None
                for key in NUTRIENTS
                for value in (item[key],)
            )
            for item in items
        )
        or any(
            _safe_number452(totals[key]) is None
            or type(coverage[key]) is not int
            or not 0 <= coverage[key] <= len(items)
            for key in NUTRIENTS
        )
        or _safe_number452(report["water_oz"]) is None
        or report["water_target_oz"] != WATER_TARGET_OZ
    ):
        raise RuntimeError("Private food response shape invalid")

    return report


def main():
    uid, private = validate_environment()
    day = parse_request452(sys.stdin.buffer.read(MAX_REQUEST + 1))
    print(json.dumps(private_food_day452(uid, private, day), sort_keys=True))


if __name__ == "__main__":
    main()
