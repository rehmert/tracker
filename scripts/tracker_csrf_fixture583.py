#!/usr/bin/env python3
"""Seed and verify isolated Release 583 vial preparation / supply accounting.

Never touches installed DEV/PROD. Requires the disposable browser QA directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

def private_data() -> Path:
    path = Path(os.environ["TRACKER_DATA_DIR"]).resolve(strict=True)
    if (path.name != "data"
        or path.parent.parent != Path("/tmp")
        or not re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}", path.parent.name)
        or os.environ.get("TRACKER_INSTANCE") != "DEV"
        or os.environ.get("TRACKER_TEST_ISOLATED") != "1"
        or os.environ.get("TRACKER_TEST_STRICT_CSRF") != "1"):
        raise RuntimeError("Refusing non-isolated fixture database")
    return path

def manifest_path(data: Path) -> Path:
    return data.parent / "csrf-fixture583.json"

def seed(data: Path) -> None:
    from app.db import SessionLocal
    from app.models import Purchase, Supply, Vial
    with SessionLocal() as db:
        vials = [db.get(Vial, i) for i in (1, 2)]
        if any(v is None or v.volume_ml is not None or v.doses for v in vials):
            raise RuntimeError("Expected two unused, unreconstituted QA fixture vials")
        purchase = Purchase(vendor="QA disposable 583", purchased_on=date.today())
        db.add(purchase)
        db.flush()
        ids = {}
        for key, kind, stock in (
            ("water", "bac_water", 10.0),
            ("needle", "needle", 10.0),
            ("swab", "swab", 10.0),
        ):
            supply = Supply(
                purchase_id=purchase.id, name="QA 583 " + key,
                kind=kind, purchased_qty=stock, remaining_qty=stock,
            )
            db.add(supply)
            db.flush()
            ids[key] = supply.id
        db.commit()
    path = manifest_path(data)
    with path.open("x", encoding="utf-8") as file:
        json.dump(ids, file, sort_keys=True)
        file.write("\n")
    path.chmod(0o600)
    print("CSRF_583_SYNTHETIC_SUPPLIES_SEEDED=YES", flush=True)

def verify(data: Path) -> None:
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Supply, SupplyUsage, PreparationEvent, PreparationSupply, Vial
    path = manifest_path(data)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise RuntimeError("Unsafe QA fixture manifest")
    ids = json.loads(path.read_text(encoding="utf-8"))
    if set(ids) != {"water", "needle", "swab"}:
        raise RuntimeError("Missing QA supply IDs")
    with SessionLocal() as db:
        supplies = {key: db.get(Supply, ident) for key, ident in ids.items()}
        expected = {"water": 6.0, "needle": 8.0, "swab": 10.0}
        for key, target in expected.items():
            item = supplies[key]
            if not item or item.name != "QA 583 " + key or abs(item.remaining_qty - target) > 1e-8:
                raise RuntimeError(f"QA supply accounting failed: {key}")
        for vid in (1, 2):
            v = db.get(Vial, vid)
            if not v or abs((v.volume_ml or 0) - 2.0) > 1e-8 or v.status != "in_use":
                raise RuntimeError(f"QA vial reconstitution failed: {vid}")
            events = list(db.scalars(select(PreparationEvent).where(
                PreparationEvent.vial_id == vid)))
            recon = [e for e in events if e.kind == "reconstitution"]
            filtering = [e for e in events if e.kind == "filtering" and "QA 583" in e.notes]
            if len(recon) != 1 or filtering:
                raise RuntimeError(f"QA preparation lifecycle failed: {vid}")
            linked = list(db.scalars(select(PreparationSupply).where(
                PreparationSupply.event_id == recon[0].id)))
            usages = [db.get(SupplyUsage, link.usage_id) for link in linked]
            if len(usages) != 1 or usages[0].supply_id != ids["needle"] or abs(usages[0].amount - 1) > 1e-8:
                raise RuntimeError(f"QA linked preparation stock failed: {vid}")
            direct = list(db.scalars(select(SupplyUsage).where(
                SupplyUsage.vial_id == vid,
                SupplyUsage.supply_id == ids["water"])))
            if len(direct) != 1 or abs(direct[0].amount - 2.0) > 1e-8:
                raise RuntimeError(f"QA BAC-water stock failed: {vid}")
    print("CSRF_583_SUPPLY_ACCOUNTING=VERIFIED", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "verify"])
    args = parser.parse_args()
    data = private_data()
    if args.action == "seed":
        seed(data)
    else:
        verify(data)

if __name__ == "__main__":
    main()
