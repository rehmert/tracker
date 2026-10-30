"""Unified read-only inventory planning dashboard."""
import csv
import io
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..templating import render
from .scheduled_forecast import build_schedule, HORIZONS
from .forecast_audit import audit_rows

router = APIRouter()

def build_planning(db):
    scheduled, warnings = build_schedule(db)
    averages = audit_rows(db, days=28)
    avg_index = {(r["compound"], r["unit"]): r for r in averages}
    scheduled_keys = set()
    rows = []
    for r in scheduled:
        key = (r["compound"], r["unit"])
        scheduled_keys.add(key)
        avg = avg_index.get(key)
        rows.append({
            "compound": r["compound"], "unit": r["unit"],
            "protocols": r["protocols"], "items": r["items"],
            "available": r["available"],
            "occurrences": r["counts"],
            "scheduled": r["demands"], "flags": r["flags"],
            "average28": avg["demand"] if avg else None,
            "average_flag": avg["flag"] if avg else "Different unit basis",
        })
    unmatched = [r for r in averages if (r["compound"], r["unit"]) not in scheduled_keys]
    return rows, warnings, unmatched

@router.get("/planning-hub")
def planning_hub(request: Request, db: Session = Depends(get_db)):
    rows, warnings, unmatched = build_planning(db)
    return render(request, "planning_hub.html", rows=rows, warnings=warnings,
                  unmatched=unmatched, horizons=HORIZONS)

@router.get("/planning-hub.csv")
def planning_hub_csv(db: Session = Depends(get_db)):
    rows, warnings, unmatched = build_planning(db)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Compound", "Unit", "Protocols", "Items", "Stock estimate",
                     "Average 28d demand", "Average forecast flag"] +
                    [f"Scheduled {h}d occurrences" for h in HORIZONS] +
                    [f"Scheduled {h}d demand" for h in HORIZONS] +
                    [f"Scheduled {h}d flag" for h in HORIZONS])
    for r in rows:
        name = r["compound"]
        if name.lstrip().startswith(("=", "+", "-", "@")):
            name = "'" + name
        writer.writerow([name, r["unit"], r["protocols"], r["items"],
                         r["available"] if r["available"] is not None else "",
                         r["average28"] if r["average28"] is not None else "",
                         r["average_flag"]] +
                        [r["occurrences"].get(h, 0) for h in HORIZONS] +
                        [r["scheduled"].get(h) if r["scheduled"].get(h) is not None else "" for h in HORIZONS] +
                        [r["flags"].get(h, "") for h in HORIZONS])
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="planning-hub.csv"'})
