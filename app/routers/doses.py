from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import Compound, DoseLog, Vial
from ..templating import render

router = APIRouter()


def _rows(db: Session, compound_id: int | None = None, limit: int = 60) -> list[dict]:
    q = select(DoseLog).join(Vial).order_by(DoseLog.taken_at.desc(), DoseLog.id.desc()).limit(limit)
    if compound_id:
        q = q.where(Vial.compound_id == compound_id)
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
                  compound_id=compound_id,
                  now=datetime.now().strftime("%Y-%m-%dT%H:%M"))


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
def create_dose(request: Request, vial_id: int = Form(...), taken_at: str = Form(""),
                amount: float = Form(...), unit: str = Form(...), kind: str = Form("dose"),
                site: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    vial = db.get(Vial, vial_id)
    if vial is None:
        return _error("Choose a vial.")
    if vial.status == "discarded":
        return _error("That vial is marked discarded.")
    if amount <= 0:
        return _error("Amount must be above 0.")
    vd = services.vial_views(db, [vial])[vial.id]
    try:
        base = U.amount_to_vial_base(amount, unit, vd.dim, vd.conc_per_ml)
        when = services.parse_datetime(taken_at)
    except ValueError as exc:  # includes UnitError
        return _error(str(exc))
    db.add(DoseLog(vial_id=vial.id, taken_at=when, entered_value=amount,
                   entered_unit=U.parse_unit(unit).name, amount_base=base,
                   kind="waste" if kind == "waste" else "dose", site=site.strip(),
                   notes=notes.strip()))
    if vial.status == "sealed":
        vial.status = "in_use"
    db.commit()
    return render(request, "_dose_rows.html", rows=_rows(db))


@router.delete("/doses/{did}")
def delete_dose(did: int, db: Session = Depends(get_db)):
    d = db.get(DoseLog, did)
    if d is None:
        raise HTTPException(404, "Entry not found")
    db.delete(d)
    db.commit()
    return HTMLResponse("")
