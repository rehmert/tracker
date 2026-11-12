from datetime import date, datetime
from math import isfinite
import json
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from .. import services, units as U, idempotency
from ..scoped_db390 import get_scoped_db390
from ..models import Blend, Compound, DoseLog, Vial, SupplyUsage, Supply, ChangeAudit, SupplyCategory
from ..inventory_lock import reserve_inventory_write, require_inventory_write
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



def _select_dose_vial(vials, views, compound_id, vial_id, planned_date,
                      planned_amount, planned_unit, recent_vial_ids=()):
    """Choose one vial for a dose form; read only, never administers anything.

    Prefer an eligible opened vial, then the lowest-ID eligible unopened
    vial. A planned amount must fit one vial. An explicit matching selection
    is retained; POST independently validates stock, unit and identity.
    """
    scheduled = compound_id is not None and bool(planned_date)
    warning = ""

    if vial_id is not None:
        explicit = next((v for v in vials if v.id == vial_id), None)
        if (explicit is not None
                and (compound_id is None or explicit.compound_id == compound_id)
                and views[explicit.id].remaining_base > 0):
            return explicit.id, ""
        if scheduled:
            warning = ("Requested vial is unavailable, empty, or belongs to a "
                       "different compound. An eligible vial is selected if possible.")

    if compound_id is None:
        return None, warning

    def can_supply(v):
        view = views[v.id]
        if view.remaining_base <= 0:
            return False
        # A calendar plan may be expressed in mass, IU, or liquid volume.
        # For all candidates, including unopened stock, ensure the entire
        # planned amount fits *one* vial. Do not guess missing concentrations.
        if (scheduled and planned_amount is not None
                and isfinite(planned_amount) and planned_amount > 0):
            try:
                base = U.amount_to_vial_base(
                    planned_amount, planned_unit, view.dim, view.conc_per_ml
                )
            except (U.UnitError, ValueError, TypeError):
                return False
            return isfinite(base) and 0 < base <= view.remaining_base + 1e-7
        return True

    opened = sorted(
        (v for v in vials if v.compound_id == compound_id
         and v.status == "in_use" and can_supply(v)),
        key=lambda v: v.id,
    )

    if opened and scheduled:
        by_id = {v.id: v for v in opened}
        for recent_id in recent_vial_ids:
            if recent_id in by_id:
                return recent_id, (
                    "Most recently logged eligible in-use vial preselected. "
                    "Confirm the physical vial before recording."
                )

    if opened:
        if scheduled and not warning:
            warning = ("First eligible in-use vial selected automatically. "
                       "Confirm the physical vial and actual administration "
                       "details before recording.")
        return opened[0].id, warning

    # Release 566: calendar handoffs must fall back to available unopened
    # stock rather than leaving the selection blank. Lowest permanent ID is
    # the oldest stocked unopened vial, independent of dropdown ordering.
    unopened = sorted(
        (v for v in vials if v.compound_id == compound_id
         and v.status == "sealed" and can_supply(v)),
        key=lambda v: v.id,
    )
    if unopened:
        if scheduled and not warning:
            warning = (
                "No eligible opened vial. Lowest-index eligible unopened "
                f"vial #{unopened[0].id} selected automatically. "
                "Confirm the physical vial before recording."
            )
        return unopened[0].id, warning

    if scheduled and not warning:
        warning = (
            "No opened or unopened vial with enough compatible stock "
            "was found for this planned dose. Choose a vial manually."
        )
    return None, warning


def _blend_remaining_display(blend: Blend, remaining_ml: float) -> str:
    """Human-readable stock for Dose Log, without changing inventory units.

    Waterfall components store content in mcg or IU, while blend draws deplete
    liquid volume. Convert the remaining fraction of the recorded contents to
    the original quantity dimension. Never combine unlike compounds/units.
    """
    fallback = f"{U._num(remaining_ml)} mL"
    if not (blend.notes or "").startswith("Waterfall:"):
        return fallback
    if not blend.final_volume_ml or blend.final_volume_ml <= 0 or not blend.components:
        return fallback
    if len({component.compound_id for component in blend.components}) != 1:
        return fallback

    try:
        dimensions = {U.parse_unit(c.target_unit).dim for c in blend.components}
    except U.UnitError:
        return fallback
    if len(dimensions) != 1:
        return fallback

    total_base = sum(c.transferred_base for c in blend.components)
    remaining_base = total_base * remaining_ml / blend.final_volume_ml
    if not isfinite(remaining_base) or remaining_base < 0:
        return fallback
    if dimensions == {"mass"}:
        return (f"{U._num(remaining_base / 1000)} mg"
                if remaining_base >= 1000
                else f"{U._num(remaining_base)} mcg")
    if dimensions == {"iu"}:
        return f"{U._num(remaining_base)} IU"
    return fallback


@router.get("/doses")
def doses_page(request: Request, compound_id: int | None = None, vial_id: int | None = None, planned_date: str = "", planned_time: str = "", planned_amount: float | None = None, planned_unit: str = "", repeat_from: int | None = None, db: Session = Depends(get_scoped_db390)):
    vials = list(db.scalars(select(Vial).where(Vial.status.in_(("sealed", "in_use")))
                            .order_by(Vial.status.desc(), Vial.id.desc())))
    views = services.vial_views(db, vials)
    # Release 564: blended/waterfall preparations are Blend records, not Vials.
    # Surface them in the normal dose-entry navigation but keep their volume-
    # based accounting and BlendDose endpoint, avoiding duplicate inventory.
    blend_candidates = list(db.scalars(
        select(Blend)
        .options(selectinload(Blend.doses), selectinload(Blend.components))
        .where(Blend.status == "in_use")
        .order_by(Blend.id.desc())
    ))
    active_blends = [
        {"blend": b, "remaining_ml": max(
            0.0, b.final_volume_ml - sum(d.volume_ml for d in b.doses)
        )}
        for b in blend_candidates
    ]
    active_blends = [
        row for row in active_blends if row["remaining_ml"] > 1e-9
    ]
    for row in active_blends:
        row["remaining_display"] = _blend_remaining_display(
            row["blend"], row["remaining_ml"]
        )
    planned_handoff = bool(planned_date) and compound_id is not None
    recent_vial_ids = []
    if planned_handoff:
        in_use_ids = [
            v.id for v in vials
            if v.compound_id == compound_id and v.status == "in_use"
        ]
        if in_use_ids:
            recent_vial_ids = list(db.scalars(
                select(DoseLog.vial_id)
                .where(DoseLog.kind == "dose", DoseLog.vial_id.in_(in_use_ids))
                .order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
                .limit(250)
            ))
    selected_vial_id, calendar_vial_notice = _select_dose_vial(
        vials, views, compound_id, vial_id, planned_date,
        planned_amount, planned_unit, recent_vial_ids,
    )
    # A calendar handoff must not offer another compound's vial.
    form_vials = (
        [v for v in vials if v.compound_id == compound_id]
        if planned_handoff else vials
    )
    planned_compound = db.get(Compound, compound_id) if planned_handoff else None

    # Historical entries can prefill a NEW record only after explicit selection.
    # Never reuse the historical timestamp, supplies, notes, or submission token.
    # A planned calendar handoff always takes precedence over history shortcuts.
    repeat_notice = ""
    repeat_site = ""
    repeat_amount = None
    repeat_unit = ""
    if repeat_from is not None and not (
        planned_date or planned_time or planned_amount is not None
        or planned_unit or vial_id is not None or compound_id is not None
    ):
        source = db.get(DoseLog, repeat_from)
        if source is None or source.kind != "dose":
            repeat_notice = "The selected historical administration is unavailable for prefill."
        else:
            matching = next((v for v in vials if v.id == source.vial_id), None)
            if matching is None:
                repeat_notice = "The historical vial is no longer available. Choose an available vial."
            else:
                try:
                    converted = U.amount_to_vial_base(
                        source.entered_value, source.entered_unit,
                        views[matching.id].dim, views[matching.id].conc_per_ml,
                    )
                    if (
                        converted > 0
                        and converted <= views[matching.id].remaining_base + 1e-7
                        and source.entered_unit in U.DOSE_UNITS
                    ):
                        selected_vial_id = matching.id
                        repeat_amount = source.entered_value
                        repeat_unit = source.entered_unit
                        repeat_site = source.site if source.site in INJECTION_SITES else ""
                        repeat_notice = (
                            "Previous recorded details loaded for review only. "
                            "Confirm the actual amount, vial, time, site and supplies before saving."
                        )
                    else:
                        repeat_notice = (
                            "Previous amount does not fit the available vial contents. "
                            "Enter the actual amount manually."
                        )
                except (ValueError, TypeError):
                    repeat_notice = "Previous entry could not be used to prefill a new record."

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
    # Read-only metadata: counted supplies require whole quantities.
    counted_supply_kinds = set(db.scalars(
        select(SupplyCategory.key).where(SupplyCategory.unit == "count")
    ))

    return render(request, "doses.html", rows=_rows(db, compound_id), vials=form_vials, views=views, active_blends=active_blends,
                  planned_handoff=planned_handoff,
                  planned_compound_name=planned_compound.name if planned_compound else "Planned compound",
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  compound_id=compound_id, sites=INJECTION_SITES,
                  now=prefill_at, submission_token=idempotency.new_token(), planned_amount=planned_amount if planned_amount is not None and planned_amount > 0 else repeat_amount, planned_unit=planned_unit or repeat_unit, repeat_site=repeat_site, repeat_notice=repeat_notice, selected_compound_id=compound_id, selected_vial_id=selected_vial_id, calendar_vial_notice=calendar_vial_notice, supplies=manual_supplies.available(db), counted_supply_kinds=counted_supply_kinds)


@router.post("/doses/preview")
def preview(request: Request, vial_id: str = Form(""), amount: str = Form(""),
            unit: str = Form("mg"), db: Session = Depends(get_scoped_db390)):
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
                db: Session = Depends(get_scoped_db390), planned_compound_id: int | None = Form(None)):
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
    if planned_compound_id is not None:
        payload["planned_compound_id"] = planned_compound_id
    state, digest = idempotency.check(db, submission_token, "dose_create", payload)
    if submission_token and state == "replay":
        db.rollback()
        return reject_dose("This entry was already recorded. Use the refreshed form to log another administration.")
    if submission_token and state != "new":
        db.rollback()
        return reject_dose("Invalid or reused submission identifier. Refresh the page.")
    vial = db.get(Vial, vial_id)
    if vial is None:
        return reject_dose("Choose a vial.")
    if planned_compound_id is not None and vial.compound_id != planned_compound_id:
        return reject_dose(
            "Selected vial belongs to a different compound than the calendar entry. "
            "Choose a vial for the planned compound."
        )
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
    # Issue a new one-use submission token only AFTER the database commits.
    # HX-Trigger-After-Settle fires after the form's existing HTMX reset.
    # A rejected or replayed request never receives a fresh token.
    response = render(request, "_dose_rows.html", rows=_rows(db))
    response.headers["HX-Trigger-After-Settle"] = json.dumps({
        "tracker:dose-saved": {
            "submission_token": idempotency.new_token(),
            "new_time": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        },
    })
    return response


@router.delete("/doses/{did}")
def delete_dose(did: int, db: Session = Depends(get_scoped_db390)):
    require_inventory_write(db)
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


def _correction_available_supplies(supplies, used):
    """Keep eligible supplies, with original usage first.

    Preserve relative database ordering within each group.
    This affects only the displayed correction picker.
    """
    eligible = [
        supply
        for supply in supplies
        if supply.remaining_qty > 0 or supply.id in used
    ]
    return sorted(
        eligible,
        key=lambda supply: supply.id not in used,
    )


@router.get("/doses/{did}/edit")
def edit_page(did: int, request: Request, db: Session = Depends(get_scoped_db390)):
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    # Match the existing server-side count-category rule.
    # Metadata only; no inventory or correction changes.
    counted_supply_kinds = set(db.scalars(
        select(SupplyCategory.key).where(SupplyCategory.unit == "count")
    ))

    used = {
        usage.supply_id: usage.amount
        for usage in db.scalars(
            select(SupplyUsage).where(SupplyUsage.dose_id == did)
        )
    }

    # Keep all known names for historical audit records.
    all_supplies = list(db.scalars(
        select(Supply).order_by(Supply.name)
    ))
    supply_names = {
        str(s.id): s.name for s in all_supplies
    }

    # Only supplies in stock or already used by this dose
    # need to appear in the correction form.
    supplies = _correction_available_supplies(
        all_supplies, used
    )

    # Corrections may move an administration only between vials containing
    # the same compound. Historical source vials remain visible even when
    # finished; new destination vials must still be usable.
    candidate_vials = list(db.scalars(
        select(Vial).where(Vial.compound_id == d.vial.compound_id)
        .order_by(Vial.id)
    ))
    vial_views = services.vial_views(db, candidate_vials)
    correction_vials = [
        {"vial": v, "remaining": vial_views[v.id].remaining_base}
        for v in candidate_vials
        if v.id == d.vial_id
        or (v.status in ("sealed", "in_use")
            and vial_views[v.id].remaining_base > 0)
    ]

    return render(request, "dose_edit.html", dose=d, correction_vials=correction_vials,
                  sites=INJECTION_SITES, supplies=supplies, used=used,
                  history=list(db.scalars(select(ChangeAudit).where(ChangeAudit.entity_type == "dose", ChangeAudit.entity_id == did).order_by(ChangeAudit.id.desc()))),
                  counted_supply_kinds=counted_supply_kinds,
                  supply_names=supply_names)

@router.post("/doses/{did}/edit")
async def edit_entry(did: int, request: Request, taken_at: str = Form(""), amount: float = Form(...),
               unit: str = Form(...), kind: str = Form("dose"), site: str = Form(""),
               notes: str = Form(""), vial_id: int | None = Form(None),
               db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        raise HTTPException(409, "Inventory is busy. Please retry.")
    d = db.get(DoseLog, did)
    if not d: raise HTTPException(404)
    back = f"/doses/{did}/edit"
    try:
        selected = await manual_supplies.selections(request, db, credits={u.supply_id:u.amount for u in db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did))})
        old_usage = list(db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did)))
        destination_id = d.vial_id if vial_id is None else vial_id
        destination = db.get(Vial, destination_id)
        if destination is None or destination.compound_id != d.vial.compound_id:
            raise ValueError("Choose a vial containing the same compound.")
        if destination.id != d.vial_id and destination.status not in ("sealed", "in_use"):
            raise ValueError("The destination vial is not available for dose corrections.")
        vd = services.vial_views(db, [destination])[destination.id]
        base = U.amount_to_vial_base(amount, unit, vd.dim, vd.conc_per_ml)
        # On the source vial, this correction releases the old recorded
        # quantity. The destination is only credited when it is the source.
        available = vd.remaining_base + (d.amount_base if destination.id == d.vial_id else 0)
        if not isfinite(base) or base <= 0 or base > available + 1e-7:
            raise ValueError("Amount exceeds available destination vial contents.")
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
        # Reassigning this FK transfers consumption automatically: vial
        # balances are calculated from their linked DoseLog rows, rather
        # than stored counters. No new dose or duplicate supply usage.
        d.vial_id = destination.id
        if destination.status == "sealed":
            destination.status = "in_use"
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
    db: Session = Depends(get_scoped_db390),
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

    # Stage 26: date-aware inventory recommendation.
    # This does not create or modify dose records.

    from app.vial_recommendation import rank_vials

    # Evaluate recorded expiration and beyond-use against the planned
    # administration date, not merely the date this page was opened.
    # Without planned context the usual current-day guidance still applies.
    reference_date = (
        date.fromisoformat(planned_params["planned_date"])
        if planned_params.get("planned_date") else date.today()
    )
    recommended_vial_id, vial_date_warnings = rank_vials(
        available_vials,
        vial_guidance,
        today=reference_date,
    )

    # Stage 27: display recorded vial dates.
    # Read-only: no inventory or dose records modified.

    from app.vial_recommendation import first_use_date

    vial_date_details = {}

    for vial in available_vials:
        vial_date_details[vial.id] = {
            "first_used": first_use_date(vial),
            "beyond_use": vial.beyond_use_on,
            "expires": vial.expires_on,
        }

    recommended_reason = ""

    if recommended_vial_id is not None:
        recommended_vial = next(
            (
                vial for vial in available_vials
                if vial.id == recommended_vial_id
            ),
            None,
        )

        if recommended_vial is not None:
            first_used = first_use_date(recommended_vial)

            if recommended_vial.status == "in_use":
                if first_used is not None:
                    recommended_reason = (
                        "In-use vial with recorded first-use date"
                    )
                else:
                    recommended_reason = (
                        "In-use vial; first-use date not recorded"
                    )
            else:
                recommended_reason = (
                    "Available sealed inventory candidate"
                )

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
        vial_date_warnings=vial_date_warnings,
        vial_date_details=vial_date_details,
        recommended_reason=recommended_reason,
    )
