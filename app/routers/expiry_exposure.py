"""Read-only future-expiration exposure; no assumptions about consumption order."""
import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Vial, DoseLog, BlendComponent, Compound
from ..templating import render
from .inventory_forecast import normalized

router = APIRouter()
HORIZONS = (7, 14, 28, 56)

def exposure_rows(db, today=None):
    today = today or date.today()
    compounds = {c.id: c.name for c in db.scalars(select(Compound)).all()}
    used = defaultdict(float)
    for record in db.scalars(select(DoseLog)).all():
        try:
            value = float(record.amount_base or 0)
            if isfinite(value) and value > 0:
                used[record.vial_id] += value
        except (ValueError, TypeError, OverflowError):
            pass
    for record in db.scalars(select(BlendComponent)).all():
        try:
            value = float(record.transferred_base or 0)
            if isfinite(value) and value > 0:
                used[record.source_vial_id] += value
        except (ValueError, TypeError, OverflowError):
            pass
    groups = defaultdict(lambda: {"eligible":0, "remaining":0.0,
                                  "unknown_dates":0, "expiring":defaultdict(float),
                                  "vials_expiring":defaultdict(int)})
    for vial in db.scalars(select(Vial)).all():
        if vial.status not in ("sealed", "in_use") or vial.closed_on:
            continue
        expiry = min((d for d in (vial.expires_on, vial.beyond_use_on) if d is not None), default=None)
        if expiry is not None and expiry < today:
            continue
        content = normalized(vial.content_value, vial.content_unit)
        if content is None:
            continue
        unit = "IU" if vial.content_unit == "IU" else "mg"
        scale = 1 if unit == "IU" else 1000
        remaining = max(0.0, content - used[vial.id]) / scale
        key = (compounds.get(vial.compound_id, f"Compound #{vial.compound_id}"), unit)
        group = groups[key]
        group["eligible"] += 1
        group["remaining"] += remaining
        if expiry is None:
            group["unknown_dates"] += 1
        else:
            for days in HORIZONS:
                # Conservative boundary: a vial dated on the horizon is
                # flagged, not assumed to remain usable that entire day.
                if expiry <= today + timedelta(days=days):
                    group["expiring"][days] += remaining
                    group["vials_expiring"][days] += 1
    rows = []
    for (name, unit), group in groups.items():
        rows.append({
            "compound":name, "unit":unit,
            "eligible":group["eligible"], "remaining":group["remaining"],
            "unknown_dates":group["unknown_dates"],
            "expiring":dict(group["expiring"]),
            "vials_expiring":dict(group["vials_expiring"]),
            "unexposed":{days:max(0.0,group["remaining"]-group["expiring"][days])
                         for days in HORIZONS},
        })
    return sorted(rows, key=lambda r:(-r["expiring"].get(28,0),r["compound"].casefold(),r["unit"]))

@router.get("/expiry-exposure")
def expiry_exposure(request:Request, db:Session=Depends(get_db)):
    return render(request,"expiry_exposure.html",rows=exposure_rows(db),horizons=HORIZONS)

@router.get("/expiry-exposure.csv")
def expiry_exposure_csv(db:Session=Depends(get_db)):
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(["Compound","Unit","Currently eligible vials","Current stock estimate",
                     "Vials without expiry/BUD"]+
                    [f"{d}d at-risk stock" for d in HORIZONS]+
                    [f"{d}d dated vials" for d in HORIZONS])
    for row in exposure_rows(db):
        name=row["compound"]
        if name.lstrip().startswith(("=","+","-","@")): name="'"+name
        writer.writerow([name,row["unit"],row["eligible"],round(row["remaining"],4),
                         row["unknown_dates"]]+
                        [round(row["expiring"].get(d,0),4) for d in HORIZONS]+
                        [row["vials_expiring"].get(d,0) for d in HORIZONS])
    return Response("\ufeff"+stream.getvalue(),media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":'attachment; filename="expiry-exposure.csv"'})
