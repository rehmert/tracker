from datetime import datetime
import json
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .. import services, units as U, idempotency
from ..db import get_db
from ..models import Compound, DoseLog, Vial, SupplyUsage, Supply, ChangeAudit
from ..inventory_lock import reserve_inventory_write
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


def _dose_snapshot(d: DoseLog, usages: list[SupplyUsage]) -> dict:
    """Capture the complete record and supply consumption for an audit event."""
    return {
        "vial_id": d.vial_id,
        "taken_at": d.taken_at.isoformat(),
        "entered_value": d.entered_value,
        "entered_unit": d.entered_unit,
        "amount_base": d.amount_base,
        "kind": d.kind,
        "site": d.site,
        "notes": d.notes,
        "supplies": {str(u.supply_id): u.amount for u in usages},
    }


def _error(msg: str) -> HTMLResponse:
    return HTMLResponse(f'<p class="error" role="alert">{escape(msg)}</p>',
                        headers={"HX-Retarget": "#form-msg", "HX-Reswap": "innerHTML"})


@router.get("/doses")
def doses_page(request: Request, compound_id: int | None = None, vial_id: int | None = None, planned_date: str = "", planned_time: str = "", planned_amount: float | None = None, planned_unit: str = "", db: Session = Depends(get_db)):
    vials = list(db.scalars(select(Vial).where(Vial.status.in_(("sealed", "in_use")))
                            .order_by(Vial.status.desc(), Vial.id.desc())))
    views = services.vial_views(db, vials)
    selected_vial_id = (
        vial_id
        if vial_id is not None
        and any(v.id == vial_id for v in vials)
        else None
    )

    if planned_date:
        try:
            scheduled = datetime.strptime(planned_date, "%Y-%m-%d")
            if planned_time:
                scheduled = datetime.strptime(planned_date + "T" + planned_time, "%Y-%m-%dT%H:%M")
            prefill_at = scheduled.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            prefill_at = datetime.now().strftime("%Y-%m-%dT%H:%M")
    else:
        prefill_at = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return render(request, "doses.html", rows=_rows(db, compound_id), vials=vials, views=views,
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  compound_id=compound_id, sites=INJECTION_SITES,
                  now=prefill_at, submission_token=idempotency.new_token(), planned_amount=planned_amount if planned_amount is not None and planned_amount > 0 else None, planned_unit=planned_unit, selected_compound_id=compound_id, selected_vial_id=selected_vial_id, supplies=manual_supplies.available(db))


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
                site: str = Form(""), notes: str = Form(""), use_remaining: str = Form(""), submission_token: str = Form(""),
                db: Session = Depends(get_db)):
    def reject_dose(message: str):
        """Release the inventory reservation before returning an error."""
        db.rollback()
        return _error(message)

    # SQLite has one writer at a time. Acquire the write reservation before
    # reading remaining inventory so competing dose requests cannot both
    # validate against the same stale quantity.
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    except OperationalError:
        db.rollback()
        return reject_dose("Inventory is busy. Please wait a moment and retry.")
    submitted_form = await request.form()
    supply_payload = sorted((k, str(v)) for k, v in submitted_form.multi_items()
                            if k == "supply_id_used" or k.startswith("supply_qty_"))
    payload = {"supplies": supply_payload, "vial_id": vial_id, "taken_at": taken_at, "amount": amount, "unit": unit, "kind": kind, "site": site, "notes": notes, "use_remaining": use_remaining}
    state, digest = idempotency.check(db, submission_token, "dose_create", payload)
    if submission_token and state == "replay":
        db.rollback()
        return reject_dose("This entry was already recorded. Refresh the page before logging another dose.")
    if submission_token and state != "new":
        db.rollback()
        return reject_dose("Invalid or reused submission identifier. Refresh the page.")
    vial = db.get(Vial, vial_id)
    if vial is None:
        return reject_dose("Choose a vial.")
    if site and site not in INJECTION_SITES:
        return reject_dose("Unknown injection site.")
    if vial.status == "discarded":
        return reject_dose("That vial is marked discarded.")
    if amount <= 0 and not use_remaining:
        return reject_dose("Amount must be above 0.")
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
        return reject_dose(str(exc))
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return reject_dose(str(exc))
    dose = DoseLog(vial_id=vial.id, taken_at=when, entered_value=amount,
                   entered_unit=U.parse_unit(unit).name, amount_base=base,
                   kind="waste" if kind == "waste" else "dose", site=site.strip(),
                   notes=notes.strip())
    db.add(dose)
    db.flush()
    manual_supplies.deduct(db, selected, dose_id=dose.id)
    if vial.status == "sealed":
        vial.status = "in_use"
    if submission_token:
        idempotency.record(db, submission_token, "dose_create", digest)
    db.commit()
    return render(request, "_dose_rows.html", rows=_rows(db))


@router.delete("/doses/{did}")
def delete_dose(did: int, db: Session = Depends(get_db)):
    if not reserve_inventory_write(db):
        raise HTTPException(409, "Inventory is busy. Please retry.")
    d = db.get(DoseLog, did)
    if d is None:
        raise HTTPException(404, "Entry not found")
    used = list(db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did)))
    db.add(ChangeAudit(entity_type="dose", entity_id=did, action="delete",
                       before_json=json.dumps(_dose_snapshot(d, used)), after_json="{}"))
    manual_supplies.restore_dose(db, did)
    db.delete(d)
    db.commit()
    return HTMLResponse("")


@router.get("/doses/{did}/edit")
def edit_page(did: int, request: Request, db: Session = Depends(get_db)):
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    return render(request, "dose_edit.html", dose=d, sites=INJECTION_SITES, supplies=list(db.scalars(select(Supply).order_by(Supply.name))), used={u.supply_id:u.amount for u in db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did))},
                  history=list(db.scalars(select(ChangeAudit).where(ChangeAudit.entity_type == "dose", ChangeAudit.entity_id == did).order_by(ChangeAudit.id.desc()))))

@router.post("/doses/{did}/edit")
async def edit_entry(did: int, request: Request, taken_at: str = Form(""), amount: float = Form(...),
               unit: str = Form(...), kind: str = Form("dose"), site: str = Form(""),
               notes: str = Form(""), db: Session = Depends(get_db)):
    if not reserve_inventory_write(db):
        raise HTTPException(409, "Inventory is busy. Please retry.")
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    back = f"/doses/{did}/edit"
    try:
        selected = await manual_supplies.selections(request, db, credits={u.supply_id:u.amount for u in db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did))})
        old_usage = list(db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did)))
        vd = services.vial_views(db, [d.vial])[d.vial_id]
        base = U.amount_to_vial_base(amount, unit, vd.dim, vd.conc_per_ml)
        if base <= 0 or base > vd.remaining_base + d.amount_base + 1e-7:
            raise ValueError("Amount exceeds available vial contents.")
        if site and site not in INJECTION_SITES: raise ValueError("Unknown injection site.")
        # Validate against stock restored from this event before mutating anything.
        original = {u.supply_id: u.amount for u in old_usage}
        for item, qty in selected:
            if qty > item.remaining_qty + original.get(item.id, 0) + 1e-9:
                raise ValueError(f"Insufficient {item.name} inventory for this correction.")
        when = services.parse_datetime(taken_at)
        before = _dose_snapshot(d, old_usage)
        for u in old_usage:
            item = db.get(Supply, u.supply_id)
            if item: item.remaining_qty += u.amount
            db.delete(u)
        for item, qty in selected:
            item.remaining_qty -= qty
            db.add(SupplyUsage(supply_id=item.id, dose_id=did, amount=qty))
        d.amount_base, d.entered_value, d.entered_unit = base, amount, U.parse_unit(unit).name
        d.taken_at, d.kind, d.site, d.notes = when, ("waste" if kind == "waste" else "dose"), site, notes.strip()
        after = _dose_snapshot(d, [SupplyUsage(supply_id=item.id, amount=qty) for item, qty in selected])
        db.add(ChangeAudit(entity_type="dose", entity_id=did, action="edit",
                           before_json=json.dumps(before), after_json=json.dumps(after)))
        db.commit()
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    return services.flash_redirect("/doses", msg="Dose entry updated.")


@router.get("/dose-workspace")
def dose_workspace(
    request: Request,
    compound_id: int | None = None,
    planned_date: str = "",
    planned_time: str = "",
    planned_amount: float | None = None,
    planned_unit: str = "",
    db: Session = Depends(get_db),
):
    """Read-only overview; recording uses the existing /doses route."""

    compounds = list(
        db.scalars(
            select(Compound).order_by(Compound.name)
        )
    )

    active_vials = list(
        db.scalars(
            select(Vial)
            .where(Vial.status.in_(("sealed", "in_use")))
            .order_by(Vial.id.desc())
        )
    )

    if compound_id is not None:
        active_vials = [
            vial for vial in active_vials
            if vial.compound_id == compound_id
        ]

    views = services.vial_views(db, active_vials)

    available_vials = [
        vial for vial in active_vials
        if views[vial.id].remaining_base > 0
    ]

    available_vials.sort(
        key=lambda vial: (
            vial.compound.name.casefold(),
            vial.id,
        )
    )

    history_query = (
        select(DoseLog)
        .join(Vial)
        .where(DoseLog.kind == "dose")
        .order_by(
            DoseLog.taken_at.desc(),
            DoseLog.id.desc(),
        )
        .limit(15)
    )

    if compound_id is not None:
        history_query = history_query.where(
            Vial.compound_id == compound_id
        )

    history = list(db.scalars(history_query))

    # Preserve validated calendar context for the
    # existing dose-recording form. No records are
    # created or modified by this workspace.

    from math import isfinite

    planned_params = {}

    if planned_date:
        try:
            datetime.strptime(planned_date, "%Y-%m-%d")
        except ValueError:
            pass
        else:
            planned_params["planned_date"] = planned_date

            if planned_time:
                try:
                    datetime.strptime(planned_time, "%H:%M")
                except ValueError:
                    pass
                else:
                    planned_params["planned_time"] = planned_time

            if (
                planned_amount is not None
                and isfinite(planned_amount)
                and planned_amount > 0
            ):
                planned_params["planned_amount"] = str(
                    planned_amount
                )

            if planned_unit in (
                "mg", "mcg", "g", "mL", "IU", "units"
            ):
                planned_params["planned_unit"] = planned_unit

    # Stage 25: read-only inventory guidance.
    #
    # Compare quantities only when the planned unit
    # can be converted using Tracker's existing unit
    # conversion service.
    #
    # Never use a guessed conversion.

    vial_guidance = {}
    recommended_vial_id = None

    planned_value = planned_params.get("planned_amount")
    planned_unit_value = planned_params.get("planned_unit")

    for vial in available_vials:
        view = views[vial.id]

        guidance = {
            "state": "unknown",
            "label": "Check units",
            "eligible": False,
        }

        if planned_value and planned_unit_value:
            try:
                required = U.amount_to_vial_base(
                    float(planned_value),
                    planned_unit_value,
                    view.dim,
                    view.conc_per_ml,
                )

                if required > 0:
                    if required <= view.remaining_base + 1e-7:
                        guidance = {
                            "state": "sufficient",
                            "label": "Sufficient",
                            "eligible": True,
                        }
                    else:
                        guidance = {
                            "state": "insufficient",
                            "label": "Insufficient",
                            "eligible": False,
                        }

            except (ValueError, TypeError, ArithmeticError):
                pass

        else:
            guidance = {
                "state": "not-planned",
                "label": "No planned amount",
                "eligible": view.remaining_base > 0,
            }

        vial_guidance[vial.id] = guidance

    # Prefer an already-open vial with sufficient
    # contents, then the oldest vial ID.
    #
    # When no planned amount exists, highlight an
    # inventory candidate without claiming dose
    # sufficiency.

    candidates = [
        vial for vial in available_vials
        if vial_guidance[vial.id]["eligible"]
    ]

    candidates.sort(
        key=lambda vial: (
            0 if vial.status == "in_use" else 1,
            vial.id,
        )
    )

    if candidates:
        recommended_vial_id = candidates[0].id

    return render(
        request,
        "dose_workspace.html",
        compounds=compounds,
        compound_id=compound_id,
        vials=available_vials,
        views=views,
        history=history,
        planned_params=planned_params,
        vial_guidance=vial_guidance,
        recommended_vial_id=recommended_vial_id,
    )
