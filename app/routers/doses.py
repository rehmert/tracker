from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import Compound, DoseLog, Vial, SupplyUsage, Supply
from .. import manual_supplies
from ..templating import render

router = APIRouter()
INJECTION_SITES = ("Abdomen upper left", "Abdomen upper right", "Abdomen lower left",
                   "Abdomen lower right", "Quadriceps left", "Quadriceps right",
                   "Glute left", "Glute right", "Other / not recorded")


def _rows(db: Session, compound_id: int | None = None, limit: int = 60) -> list[dict]:
    q = select(DoseLog).join(Vial).order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
    if compound_id:
        q = q.where(Vial.compound_id == compound_id)
    q = q.limit(limit)
    doses = list(db.scalars(q))
    views = services.vial_views(db)
    return [{"dose": d, "vial": d.vial, "vd": views[d.vial_id],
             "cost": views[d.vial_id].cost_per_base * d.amount_base} for d in doses]


def _error(msg: str) -> HTMLResponse:
    return HTMLResponse(f'<p class="error" role="alert">{escape(msg)}</p>',
                        headers={"HX-Retarget": "#form-msg", "HX-Reswap": "innerHTML"})


@router.get("/doses")
def doses_page(request: Request, compound_id: int | None = None, db: Session = Depends(get_db)):
    vials = list(db.scalars(select(Vial).where(Vial.status.in_(("sealed", "in_use")))
                            .order_by(Vial.status.desc(), Vial.id.desc())))
    views = services.vial_views(db, vials)
    return render(request, "doses.html", rows=_rows(db, compound_id), vials=vials, views=views,
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  compound_id=compound_id, sites=INJECTION_SITES,
                  now=datetime.now().strftime("%Y-%m-%dT%H:%M"), supplies=manual_supplies.available(db))


@router.post("/doses/preview")
def preview(request: Request, vial_id: str = Form(""), amount: str = Form(""),
            unit: str = Form("mg"), db: Session = Depends(get_db)):
    """Live conversion for the log form. Arithmetic on what was typed; nothing is saved."""
    try:
        vid, value = int(vial_id), float(amount)
    except ValueError:
        return HTMLResponse("")
    vial = db.get(Vial, vid)
    if vial is None:
        return HTMLResponse("")
    vd = services.vial_views(db, [vial])[vid]
    ctx = {"vd": vd, "unit": unit, "value": value}
    try:
        base = U.amount_to_vial_base(value, unit, vd.dim, vd.conc_per_ml)
    except U.UnitError as exc:
        return render(request, "_dose_preview.html", error=str(exc), **ctx)
    draw = base / vd.conc_per_ml if vd.conc_per_ml else None
    return render(request, "_dose_preview.html", error=None, base=base,
                  cost=vd.cost_per_base * base, after=vd.remaining_base - base, draw=draw,
                  marks=U.ml_to_syringe_units(draw) if draw is not None else None, **ctx)


@router.post("/doses")
async def create_dose(request: Request, vial_id: int = Form(...), taken_at: str = Form(""),
                amount: float = Form(...), unit: str = Form(...), kind: str = Form("dose"),
                site: str = Form(""), notes: str = Form(""), use_remaining: str = Form(""),
                db: Session = Depends(get_db)):
    vial = db.get(Vial, vial_id)
    if vial is None:
        return _error("Choose a vial.")
    if site and site not in INJECTION_SITES:
        return _error("Unknown injection site.")
    if vial.status == "discarded":
        return _error("That vial is marked discarded.")
    if amount <= 0 and not use_remaining:
        return _error("Amount must be above 0.")
    vd = services.vial_views(db, [vial])[vial.id]
    try:
        if use_remaining:
            base = vd.remaining_base
            if base <= 0: raise ValueError("No contents remain.")
            amount, unit = (base, "mcg" if vd.dim == "mass" else "IU")
        else:
            base = U.amount_to_vial_base(amount, unit, vd.dim, vd.conc_per_ml)
        if base <= 0 or base > vd.remaining_base + 1e-7:
            raise ValueError("Amount exceeds remaining vial contents.")
        when = services.parse_datetime(taken_at)
    except ValueError as exc:  # includes UnitError
        return _error(str(exc))
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return _error(str(exc))
    dose = DoseLog(vial_id=vial.id, taken_at=when, entered_value=amount,
                   entered_unit=U.parse_unit(unit).name, amount_base=base,
                   kind="waste" if kind == "waste" else "dose", site=site.strip(),
                   notes=notes.strip())
    db.add(dose)
    db.flush()
    manual_supplies.deduct(db, selected, dose_id=dose.id)
    if vial.status == "sealed":
        vial.status = "in_use"
    db.commit()
    return render(request, "_dose_rows.html", rows=_rows(db))


@router.delete("/doses/{did}")
def delete_dose(did: int, db: Session = Depends(get_db)):
    d = db.get(DoseLog, did)
    if d is None:
        raise HTTPException(404, "Entry not found")
    manual_supplies.restore_dose(db, did)
    db.delete(d)
    db.commit()
    return HTMLResponse("")


@router.get("/doses/{did}/edit")
def edit_page(did: int, request: Request, db: Session = Depends(get_db)):
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    return render(request, "dose_edit.html", dose=d, sites=INJECTION_SITES)

@router.post("/doses/{did}/edit")
def edit_entry(did: int, taken_at: str = Form(""), amount: float = Form(...),
               unit: str = Form(...), kind: str = Form("dose"), site: str = Form(""),
               notes: str = Form(""), db: Session = Depends(get_db)):
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    back = f"/doses/{did}/edit"
    try:
        vd = services.vial_views(db, [d.vial])[d.vial_id]
        base = U.amount_to_vial_base(amount, unit, vd.dim, vd.conc_per_ml)
        if base <= 0 or base > vd.remaining_base + d.amount_base + 1e-7:
            raise ValueError("Amount exceeds available vial contents.")
        if site and site not in INJECTION_SITES: raise ValueError("Unknown injection site.")
        d.amount_base, d.entered_value, d.entered_unit = base, amount, U.parse_unit(unit).name
        d.taken_at, d.kind, d.site, d.notes = services.parse_datetime(taken_at), ("waste" if kind == "waste" else "dose"), site, notes.strip()
        db.commit()
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    return services.flash_redirect("/doses", msg="Dose entry updated.")
