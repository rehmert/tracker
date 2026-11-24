"""Release 766: bounded, atomic CSV/manual daily device summary importer.

Import only explicit daily aggregates, never raw or timestamped CGM readings.
An existing source/date row is not overwritten without a deliberate checkbox.
"""
from __future__ import annotations

import csv
from datetime import date
import io
import math

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..device_models766 import DeviceDay766
from ..scoped_db390 import get_scoped_db390
from ..templating import render

router = APIRouter()
MAX_BYTES = 262144
MAX_ROWS = 2000
COLUMNS = ("date", "steps", "sleep_hours", "resting_bpm", "glucose_avg_mgdl")
RANGES = {
    "steps": (0, 100000),
    "sleep_hours": (0, 24),
    "resting_bpm": (20, 250),
    "glucose_avg_mgdl": (20, 650),
}


def parse_day766(raw):
    try:
        day = date.fromisoformat(str(raw or "").strip())
    except (ValueError, TypeError):
        raise HTTPException(422, "Use an ISO date (YYYY-MM-DD)") from None
    if not date(2000, 1, 1) <= day <= date.today():
        raise HTTPException(422, "Import date must be between 2000 and today")
    return day


def parse_measure766(key, raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        number = float(raw)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, f"Invalid {key} value") from None
    low, high = RANGES[key]
    if not math.isfinite(number) or not low <= number <= high:
        raise HTTPException(422, f"{key} outside expected range")
    if key == "steps":
        if number != int(number):
            raise HTTPException(422, "Steps must be whole numbers")
        return int(number)
    return round(number, 4)


def normalize766(item):
    day = parse_day766(item.get("date"))
    values = {key: parse_measure766(key, item.get(key))
              for key in RANGES}
    if all(v is None for v in values.values()):
        raise HTTPException(422, "Each row needs at least one measured value")
    return {"measured_on": day, **values}


def parse_csv766(contents):
    if len(contents) > MAX_BYTES:
        raise HTTPException(413, "CSV is larger than 256 KiB")
    try:
        decoded = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8") from None
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(422, "CSV header missing")
    headers = [name.strip() for name in reader.fieldnames]
    if len(headers) != len(set(headers)) or "date" not in headers:
        raise HTTPException(422, "CSV requires a unique date column")
    if any(name not in COLUMNS for name in headers):
        raise HTTPException(422, "Unknown CSV header; use the documented daily columns")
    if not any(name in headers for name in RANGES):
        raise HTTPException(422, "CSV needs at least one measurement column")
    items = []
    seen = set()
    for row in reader:
        if len(items) >= MAX_ROWS:
            raise HTTPException(422, "CSV exceeds 2,000 daily records")
        if None in row:
            raise HTTPException(422, "A CSV row has more cells than the header")
        payload = {str(k).strip():v for k,v in row.items()}
        parsed = normalize766(payload)
        if parsed["measured_on"] in seen:
            raise HTTPException(422, "CSV contains duplicate dates")
        seen.add(parsed["measured_on"])
        items.append(parsed)
    if not items:
        raise HTTPException(422, "CSV contains no device records")
    return items


def store766(db: Session, source, records, replace=False):
    source = str(source or "").strip()
    if not 1 <= len(source) <= 80 or any(ord(ch) < 32 for ch in source):
        raise HTTPException(422, "Source must be 1–80 printable characters")
    dates = {record["measured_on"] for record in records}
    if len(dates) != len(records):
        raise HTTPException(422, "Duplicate dates are not allowed per source")
    existing = {row.measured_on: row for row in db.scalars(
        select(DeviceDay766).where(
            DeviceDay766.source == source,
            DeviceDay766.measured_on.in_(dates),
        )
    )}
    added = updated = skipped = 0
    for record in records:
        prior = existing.get(record["measured_on"])
        if prior is not None:
            if not replace:
                skipped += 1
                continue
            for key in RANGES:
                setattr(prior, key, record[key])
            updated += 1
        else:
            db.add(DeviceDay766(source=source, **record))
            added += 1
    db.commit()
    return dict(added=added, updated=updated, skipped=skipped)


@router.get("/device-import")
def device_page766(
    request: Request, db: Session = Depends(get_scoped_db390)
):
    rows = list(db.scalars(
        select(DeviceDay766)
        .order_by(DeviceDay766.measured_on.desc(), DeviceDay766.id.desc())
        .limit(100)
    ))
    return render(request, "device_import766.html", rows=rows, today=date.today().isoformat())


@router.post("/device-import")
async def device_save766(
    source: str = Form(...), replace: bool = Form(False),
    uploaded: UploadFile | None = File(None),
    day: str = Form(""), steps: str = Form(""),
    sleep_hours: str = Form(""), resting_bpm: str = Form(""),
    glucose_avg_mgdl: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    if uploaded is not None and uploaded.filename:
        if not uploaded.filename.lower().endswith(".csv"):
            raise HTTPException(422, "Upload a .csv file")
        raw = await uploaded.read(MAX_BYTES + 1)
        records = parse_csv766(raw)
    else:
        records = [normalize766({
            "date": day, "steps": steps, "sleep_hours": sleep_hours,
            "resting_bpm": resting_bpm,
            "glucose_avg_mgdl": glucose_avg_mgdl,
        })]
    counts = store766(db, source, records, replace)
    return RedirectResponse(
        f"/device-import?added={counts['added']}&updated={counts['updated']}&skipped={counts['skipped']}",
        status_code=303,
    )


@router.post("/device-import/{row_id}/delete")
def device_delete766(row_id: int, db: Session = Depends(get_scoped_db390)):
    row = db.get(DeviceDay766, row_id)
    if row is None:
        raise HTTPException(404, "Device reading not found")
    db.delete(row)
    db.commit()
    return RedirectResponse("/device-import?deleted=1", status_code=303)
