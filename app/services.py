"""Glue between the ORM and the pure calculation modules."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import calc, charts, config, units as U
from .models import Compound, DoseLog, LabReport, Purchase, Vial


# ------------------------------------------------------------------ parsing
def to_cents(text: str | None) -> int:
    s = (text or "").strip().replace(",", "").lstrip("$€£")
    if not s:
        return 0
    try:
        return int((Decimal(s) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        raise ValueError(f"'{text}' is not a valid amount of money.")


def cents_input(cents: int | float | None) -> str:
    return "" if cents is None else f"{cents / 100:.2f}"


def parse_date(text: str | None) -> date | None:
    text = (text or "").strip()
    return date.fromisoformat(text) if text else None


def parse_datetime(text: str | None) -> datetime:
    text = (text or "").strip()
    return datetime.fromisoformat(text) if text else datetime.now().replace(microsecond=0)


def flash_redirect(url: str, msg: str = "", err: str = "") -> RedirectResponse:
    key, val = ("err", err) if err else ("msg", msg)
    sep = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{sep}{key}={quote(val)}" if val else url, status_code=303)


# -------------------------------------------------------------- vial maths
def effective_content(vial: Vial) -> tuple[float, str]:
    """(content in base units, dimension). Uses the newest COA's reported
    content when the vial is set to trust it, otherwise the label claim."""
    value, unit = vial.content_value, vial.content_unit
    if vial.use_coa_content:
        for coa in vial.coas:  # newest first
            if coa.reported_content_value and coa.reported_content_unit:
                value, unit = coa.reported_content_value, coa.reported_content_unit
                break
    return U.to_base(value, unit)


def vial_views(db: Session, vials: list[Vial] | None = None) -> dict[int, calc.VialData]:
    if vials is None:
        vials = list(db.scalars(select(Vial).order_by(Vial.id.desc())))
    consumed = dict(db.execute(
        select(DoseLog.vial_id, func.sum(DoseLog.amount_base)).group_by(DoseLog.vial_id)).all())
    landed_cache: dict[int, dict[int, float]] = {}
    out: dict[int, calc.VialData] = {}
    for v in vials:
        if v.purchase is None:
            landed = float(v.unit_price_cents)
        else:
            p = v.purchase
            if p.id not in landed_cache:
                landed_cache[p.id] = calc.allocate_landed(
                    {x.id: x.unit_price_cents for x in p.vials},
                    p.shipping_cents, p.tax_cents, p.discount_cents)
            landed = landed_cache[p.id][v.id]
        base, dim = effective_content(v)
        out[v.id] = calc.VialData(v.id, v.compound_id, dim, base, v.volume_ml, v.status,
                                  landed, float(consumed.get(v.id) or 0.0))
    return out


def compound_refs(db: Session) -> dict[int, calc.CompoundRef]:
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    vials = list(db.scalars(select(Vial)))
    views = vial_views(db, vials)
    since = datetime.now() - timedelta(days=28)
    logged = {}
    rows = db.execute(
        select(Vial.compound_id, func.sum(DoseLog.amount_base))
        .join(DoseLog, DoseLog.vial_id == Vial.id)
        .where(DoseLog.kind == "dose", DoseLog.taken_at >= since)
        .group_by(Vial.compound_id)).all()
    for cid, total in rows:
        logged[cid] = float(total or 0.0)
    refs = {}
    for c in compounds:
        cv = [views[v.id] for v in vials if v.compound_id == c.id]
        refs[c.id] = calc.build_compound_ref(c.id, c.name, cv, logged.get(c.id, 0.0))
    return refs


# ------------------------------------------------------------------ uploads
_MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}
_MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _magic_ok(ext: str, head: bytes) -> bool:
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return any(head.startswith(m) for m in _MAGIC[ext])


async def save_upload(file: UploadFile, directory: Path | None = None) -> dict:
    """Stream an upload to disk with a size cap, extension allow-list and
    magic-byte check. Stored under a random name; the original is kept for display."""
    original = Path(file.filename or "").name
    ext = Path(original).suffix.lower()
    if ext not in config.ALLOWED_UPLOAD_EXT:
        raise ValueError("Upload a PDF, PNG, JPG or WEBP file.")
    stored = f"{uuid4().hex}{ext}"
    path = (directory or config.UPLOAD_DIR) / stored
    digest, size, head = hashlib.sha256(), 0, b""
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise ValueError(f"File is larger than {config.MAX_UPLOAD_BYTES // 2**20} MB.")
                if not head:
                    head = chunk[:16]
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise ValueError("The file is empty.")
        if not _magic_ok(ext, head):
            raise ValueError("The file's contents don't match its extension.")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"original_name": original or stored, "stored_name": stored,
            "content_type": _MIME[ext], "size_bytes": size, "sha256": digest.hexdigest()}


def delete_stored_file(stored_name: str, directory: Path | None = None) -> None:
    ((directory or config.UPLOAD_DIR) / stored_name).unlink(missing_ok=True)


# ------------------------------------------------------------------- events
def _noon(d: date) -> datetime:
    return datetime.combine(d, time(12))


def events_between(db: Session, start: datetime, end: datetime) -> list[charts.Event]:
    """Dose entries (one lane per compound) and vial / purchase / lab markers that
    fall inside [start, end], for overlaying on charts."""
    events: list[charts.Event] = []

    rows = db.execute(
        select(DoseLog, Compound.name)
        .join(Vial, DoseLog.vial_id == Vial.id).join(Compound, Vial.compound_id == Compound.id)
        .where(DoseLog.kind == "dose", DoseLog.taken_at >= start, DoseLog.taken_at <= end)
        .order_by(DoseLog.taken_at)).all()
    for d, name in rows:
        events.append(charts.Event(d.taken_at, "dose",
                                   f"{name}: {d.entered_value:g} {d.entered_unit}", name))

    use = {vid: (first, last) for vid, first, last in db.execute(
        select(DoseLog.vial_id, func.min(DoseLog.taken_at), func.max(DoseLog.taken_at))
        .where(DoseLog.kind == "dose").group_by(DoseLog.vial_id)).all()}
    for v in db.scalars(select(Vial)):
        name = f"{v.compound.name} {v.label or '#' + str(v.id)}"
        if v.reconstituted_on:
            events.append(charts.Event(_noon(v.reconstituted_on), "marker", name, mark="R"))
        if v.id in use:
            first, last = use[v.id]
            events.append(charts.Event(first, "marker", name, mark="S"))
            if v.status in ("finished", "discarded"):
                events.append(charts.Event(last, "marker", name, mark="F"))
    for p in db.scalars(select(Purchase)):
        events.append(charts.Event(_noon(p.purchased_on), "marker", f"Purchase from {p.vendor}", mark="P"))
    for r in db.scalars(select(LabReport)):
        events.append(charts.Event(_noon(r.drawn_on), "marker",
                                   f"Lab draw{': ' + r.lab_name if r.lab_name else ''}", mark="L"))
    return [e for e in events if start <= e.at <= end]
