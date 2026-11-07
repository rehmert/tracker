"""Release 454: bounded, isolated seven-day food-history worker.

One subprocess handles the complete weekly request.
No HTTP listener, database writes, user-selected paths or SQL.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta

from .worker_food452 import (
    MAX_ROWS,
    NUTRIENTS,
    FIELDS,
    WATER_TARGET_OZ,
    _safe_number452,
    private_food_day452,
    validate_day452,
)
from .worker_probe428 import validate_environment

ACTION = "food_week"
MAX_REQUEST = 128


def days454(end_day):
    ending = date.fromisoformat(validate_day452(end_day))
    if ending.toordinal() < 7:
        raise ValueError("Weekly date outside supported range")
    return [
        (ending - timedelta(days=6 - i)).isoformat()
        for i in range(7)
    ]


def parse_request454(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("Invalid weekly request length")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate weekly request key")
            result[key] = value
        return result

    try:
        message = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=unique,
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid weekly request") from exc

    if (
        type(message) is not dict
        or set(message) != {"action", "day"}
        or message["action"] != ACTION
    ):
        raise ValueError("Unsupported weekly request")

    day = validate_day452(message["day"])
    days454(day)
    return day


def private_week454(uid, private, end_day):
    reports = [
        private_food_day452(uid, private, day)
        for day in days454(end_day)
    ]
    return {
        "mode": "offline-food-week454",
        "user_id": uid,
        "end_day": end_day,
        "reports": reports,
    }


def validate_response454(payload, uid, end_day):
    expected = days454(end_day)

    if (
        type(payload) is not dict
        or set(payload) != {
            "mode", "user_id", "end_day", "reports"
        }
        or payload["mode"] != "offline-food-week454"
        or type(payload["user_id"]) is not int
        or payload["user_id"] != uid
        or payload["end_day"] != end_day
        or type(payload["reports"]) is not list
        or len(payload["reports"]) != 7
    ):
        raise RuntimeError("Invalid private weekly response")

    reports = payload["reports"]

    daily_fields = {
        "mode", "user_id", "day", "items", "totals",
        "coverage", "water_oz", "water_target_oz",
        "has_more", "login_enabled",
        "http_listener_started",
    }

    for day, report in zip(expected, reports):
        if (
            type(report) is not dict
            or set(report) != daily_fields
            or report["mode"] != "offline-food-day452"
            or type(report["user_id"]) is not int
            or report["user_id"] != uid
            or report["day"] != day
            or report["login_enabled"] is not False
            or report["http_listener_started"] is not False
            or type(report["has_more"]) is not bool
            or report["water_target_oz"] != WATER_TARGET_OZ
            or _safe_number452(report["water_oz"]) is None
        ):
            raise RuntimeError("Private weekly day identity mismatch")

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
        ):
            raise RuntimeError("Invalid weekly nutrient structure")

        for key in NUTRIENTS:
            if (
                _safe_number452(totals[key]) is None
                or type(coverage[key]) is not int
                or not 0 <= coverage[key] <= len(items)
            ):
                raise RuntimeError("Invalid weekly nutrient totals")

        for item in items:
            if (
                type(item) is not dict
                or set(item) != FIELDS
                or type(item["name"]) is not str
                or len(item["name"]) > 160
                or type(item["meal"]) is not str
                or len(item["meal"]) > 40
                or _safe_number452(item["servings"]) is None
                or not 0 < item["servings"] <= 100
            ):
                raise RuntimeError("Invalid weekly food record")

            for key in NUTRIENTS:
                value = item[key]
                if value is not None and _safe_number452(value) is None:
                    raise RuntimeError("Invalid weekly food nutrient")

    return reports


def read_food_week454(user_id, end_day, data_root=None):
    end_day = validate_day452(end_day)
    days454(end_day)

    from .user_accounts427 import secondary_id
    from .worker_scope428 import (
        SOURCE_ROOT, worker_environment428,
    )

    uid = secondary_id(user_id)
    env = worker_environment428(uid, data_root)

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_week454"],
        input=json.dumps(
            {"action": ACTION, "day": end_day},
            separators=(",", ":"),
        ),
        cwd=SOURCE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    if result.returncode:
        raise RuntimeError("Private weekly worker unavailable")

    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid private weekly response") from exc

    return validate_response454(payload, uid, end_day)


def main():
    uid, private = validate_environment()
    end_day = parse_request454(
        sys.stdin.buffer.read(MAX_REQUEST + 1)
    )
    result = private_week454(uid, private, end_day)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
