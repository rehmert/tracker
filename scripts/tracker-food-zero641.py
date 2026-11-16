#!/usr/bin/env python3
"""Release 641: idempotent saved-food unknown-to-zero backfill.

Dry run by default. An executed run on DEV/PROD makes and verifies its own
consistent SQLite/uploads backup before changing any product nutrient JSON.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import socket
from sqlalchemy import text

from app.routers.food import NUTRIENTS

UNKNOWN = frozenset({"", "unknown", "null", "none", "n/a", "not reported", "?"})


def normalize_row641(raw):
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid stored nutrient JSON") from exc
    if type(data) is not dict:
        raise ValueError("Stored nutrient data is not an object")
    changed = False
    for key in NUTRIENTS:
        current = data.get(key)
        if current is None or (
            type(current) is str and current.strip().casefold() in UNKNOWN
        ):
            data[key] = 0.0
            changed = True
        elif type(current) in (int, float):
            if not math.isfinite(current) or current < 0 or current > 100000:
                raise ValueError(f"Invalid numeric value for {key}")
        elif type(current) is str:
            # Historical records sometimes contain numeric strings. Keep their
            # original payload: this backfill only replaces unknowns.
            try:
                number = float(current)
            except (ValueError, OverflowError) as exc:
                raise ValueError(f"Unrecognized nutrient value for {key}") from exc
            if not math.isfinite(number) or number < 0 or number > 100000:
                raise ValueError(f"Invalid numeric value for {key}")
        else:
            raise ValueError(f"Unsupported nutrient value for {key}")
    return (json.dumps(data, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) if changed else raw), changed


def normalize_saved_foods641(db_engine, *, execute=False):
    # A single read/write transaction guarantees all-or-nothing changes and
    # detects concurrently edited rows without rewriting their newer values.
    with db_engine.begin() as db:
        items = db.execute(text(
            "SELECT id, nutrients FROM tracker_food_products ORDER BY id"
        )).all()
        if len(items) > 100000:
            raise ValueError("More than 100000 products; separate review required")
        updates = []
        for product_id, original in items:
            changed_json, changed = normalize_row641(original)
            if changed:
                updates.append((product_id, original, changed_json))
        if execute:
            for product_id, original, changed_json in updates:
                result = db.execute(text("""
                    UPDATE tracker_food_products SET nutrients=:new
                    WHERE id=:id AND nutrients=:old
                """), {"new": changed_json, "id": product_id,
                       "old": original})
                if result.rowcount != 1:
                    raise ValueError("Saved food changed; rolled back all updates")
    return {"examined": len(items), "changed": len(updates),
            "executed": bool(execute)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Back up live data and commit the verified changes")
    parser.add_argument("--instance", choices=("DEV", "PROD"), required=True)
    args = parser.parse_args(argv)
    actual = socket.gethostname().split(".")[0]
    if actual != "tracker-" + args.instance.lower() or os.geteuid() != 0:
        parser.error("Run as root on the explicitly selected Tracker host")
    from app import config
    from app.db import engine
    if config.instance_label() != args.instance:
        parser.error("TRACKER_INSTANCE environment label mismatch")
    if not config.DB_PATH.is_file():
        parser.error("Refusing to create a missing Tracker database")
    # First verify all existing rows; never create a backup for input which
    # already fails semantic validation.
    preview = normalize_saved_foods641(engine)
    print("FOOD641_PRODUCTS_EXAMINED=" + str(preview["examined"]), flush=True)
    print("FOOD641_PRODUCTS_TO_NORMALIZE=" + str(preview["changed"]), flush=True)
    if not args.execute:
        print("FOOD641_DRY_RUN=PASSED (no mutation)", flush=True)
        return 0
    from app.backup import create_backup, verify_backup
    archive = create_backup()
    verify_backup(archive)
    print("FOOD641_VERIFIED_BACKUP=" + str(archive), flush=True)
    result = normalize_saved_foods641(engine, execute=True)
    print("FOOD641_PRODUCTS_UPDATED=" + str(result["changed"]), flush=True)
    print("FOOD641_BACKFILL=PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
