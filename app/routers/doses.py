from datetime import date, datetime
from math import isfinite
import json
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from .. import services, units as U, idempotency
from ..scoped_db390 import get_scoped_db390
from ..models import Blend, BlendDose, Compound, DoseLog, Vial, SupplyUsage, Supply, ChangeAudit, SupplyCategory
from ..audit_helpers import record
from ..blend_administration_view import blend_history
from ..blend_dose_unified710 import (
    source_identity710, remaining_blend_ml710, constituent_concentrations710,
    resolve_blend_draw710,
)
from ..inventory_lock import reserve_inventory_write, require_inventory_write
from ..blend_dose_identity711 import next_blend_dose_id711
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
def doses_page(request: Request, compound_id: int | None = None, vial_id: int | None = None, source: str = "", planned_date: str = "", planned_time: str = "", planned_amount: float | None = None, planned_unit: str = "", repeat_from: int | None = None, history_date: str = "", history_source: str = "all", history_kind: str = "all", db: Session = Depends(get_scoped_db390)):
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
        row["compound_names"] = ", ".join(sorted({
            c.compound.name for c in row["blend"].components if c.compound
        }))
        row["compound_ids"] = {c.compound_id for c in row["blend"].components}
        row["mixed"] = len(row["compound_ids"]) > 1
    planned_handoff = bool(planned_date) and compound_id is not None
    if planned_handoff:
        active_blends = [
            row for row in active_blends
            if any(component.compound_id == compound_id
                   for component in row["blend"].components)
        ]
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
    # Prefer an explicitly selected prepared physical vial; otherwise a
    # planned dose may preselect a compatible blend when no ordinary vial
    # can supply the plan. POST validates identity/quantity independently.
    selected_blend_id = None
    if source:
        try:
            requested_kind, requested_id = source_identity710(source)
            if requested_kind == "blend" and any(
                row["blend"].id == requested_id for row in active_blends
            ):
                selected_blend_id = requested_id
                selected_vial_id = None
        except ValueError:
            pass
    if selected_blend_id is None and planned_handoff and selected_vial_id is None:
        for row in active_blends:
            try:
                # A multi-compound plan must not be silently reinterpreted
                # as a single-mass draw of the mixture.
                if planned_amount is not None and planned_amount > 0:
                    resolve_blend_draw710(
                        row["blend"], planned_amount, planned_unit
                    )
                selected_blend_id = row["blend"].id
                calendar_vial_notice = (
                    "Prepared blend selected. Verify all constituents and "
                    "the actual withdrawn volume before logging."
                )
                break
            except ValueError:
                continue
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
                        and source.entered_unit in U.WITHDRAW_UNITS
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

    # Read-only combined recent history. Never synthesize a new DoseLog for
    # a blend: one physical BlendDose remains one display row.
    vial_rows = _rows(db, compound_id)
    blend_rows = blend_history(db, compound_id)
    combined = [
        {"source": "vial", "when": row["dose"].taken_at, "vial": row,
         "kind": row["dose"].kind, "id": row["dose"].id}
        for row in vial_rows
    ] + [
        {"source": "blend", "when": row["draw"].taken_at, "blend": row,
         "kind": row["draw"].kind, "id": row["draw"].id}
        for row in blend_rows
    ]
    from datetime import date as _date
    if history_date:
        try:
            _date.fromisoformat(history_date)
        except ValueError:
            history_date = ""
    if history_source not in ("all", "vial", "blend"):
        history_source = "all"
    if history_kind not in ("all", "dose", "waste"):
        history_kind = "all"
    combined = [
        row for row in combined
        if (history_source == "all" or row["source"] == history_source)
        and (history_kind == "all" or row["kind"] == history_kind)
        and (not history_date or row["when"].date().isoformat() == history_date)
    ]
    combined.sort(key=lambda row: (row["when"], row["id"]), reverse=True)
    return render(request, "doses.html", rows=vial_rows, blend_rows=blend_rows,
                  combined_history=combined, history_date=history_date,
                  history_source=history_source, history_kind=history_kind,
                  vials=form_vials, views=views, active_blends=active_blends,
                  selected_blend_id=selected_blend_id,
                  planned_handoff=planned_handoff, planned_date=planned_date, planned_time=planned_time,
                  planned_compound_name=planned_compound.name if planned_compound else "Planned compound",
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                  compound_id=compound_id, sites=INJECTION_SITES,
                  now=prefill_at, submission_token=idempotency.new_token(), planned_amount=planned_amount if planned_amount is not None and planned_amount > 0 else repeat_amount, planned_unit=planned_unit or repeat_unit, repeat_site=repeat_site, repeat_notice=repeat_notice, selected_compound_id=compound_id, selected_vial_id=selected_vial_id, calendar_vial_notice=calendar_vial_notice, supplies=manual_supplies.available(db), counted_supply_kinds=counted_supply_kinds)


@router.post("/doses/preview")
def preview(request: Request, vial_id: str = Form(""), amount: str = Form(""),
            unit: str = Form("mg"), db: Session = Depends(get_scoped_db390)):
    """Live conversion for the log form. Arithmetic on what was typed; nothing is saved."""
    try:
        kind, source_id = source_identity710(vial_id)
        value = float(amount)
    except (ValueError, TypeError):
        return HTMLResponse("")
    if kind == "blend":
        blend = db.get(Blend, source_id)
        if blend is None:
            return HTMLResponse("")
        try:
            plan = resolve_blend_draw710(blend, value, unit)
        except (ValueError, TypeError) as exc:
            return render(request, "_blend_dose_preview710.html",
                          error=str(exc))
        return render(request, "_blend_dose_preview710.html",
                      error=None, plan=plan, blend=blend)
    vid = source_id
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
async def create_dose(request: Request, vial_id: str = Form(...), taken_at: str = Form(""),
                amount: float = Form(...), unit: str = Form(...), kind: str = Form("dose"),
                site: str = Form(""), notes: str = Form(""), use_remaining: str = Form(""), submission_token: str = Form(""),
                db: Session = Depends(get_scoped_db390), planned_compound_id: int | None = Form(None),
                calendar_item_id: int | None = Form(None), calendar_date: str = Form(""),
                calendar_snapshot: str = Form(""), calendar_clock: str = Form(""),
                calendar_origin: str = Form("")):
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
    calendar_return = ""
    if calendar_item_id is not None:
        from ..calendar_quick_dose786 import quick_plan786, dose_return790, parse_clock786
        try:
            day = date.fromisoformat(calendar_date)
            plan = quick_plan786(db, calendar_item_id, day)
            source = plan["source"]
            if not source or not calendar_snapshot or plan["snapshot"] != calendar_snapshot:
                raise ValueError("Schedule or inventory changed. Return to Calendar and reopen this dose.")
            if (vial_id != source["key"] or amount != source["amount"] or unit != source["unit"]
                    or kind != "dose" or notes or use_remaining or not submission_token
                    or any(k == "supply_id_used" or k.startswith("supply_qty_")
                           for k in submitted_form)):
                raise ValueError("Quick entry accepts changes to time and injection site only.")
            taken_at = parse_clock786(calendar_clock, day).isoformat(timespec="minutes")
            planned_compound_id = plan["event"]["compound_id"]
            calendar_return = dose_return790(day, calendar_origin)
        except (ValueError, TypeError, OverflowError) as exc:
            return reject_dose(str(exc))
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
    try:
        source_kind, source_pk = source_identity710(vial_id)
    except ValueError as exc:
        return reject_dose(str(exc))
    if site and site not in INJECTION_SITES:
        return reject_dose("Unknown injection site.")
    if kind not in ("dose", "waste"):
        return reject_dose("Choose a valid administration or discard record type.")
    if use_remaining not in ("", "yes"):
        return reject_dose("Invalid remaining-contents selection.")

    if source_kind == "blend":
        blend = db.get(Blend, source_pk)
        if blend is None:
            return reject_dose("Choose an available prepared blend.")
        if (planned_compound_id is not None and
                not any(c.compound_id == planned_compound_id
                        for c in blend.components)):
            return reject_dose(
                "Selected blend does not contain the planned compound."
            )
        try:
            draw = resolve_blend_draw710(
                blend, amount, unit, use_remaining == "yes"
            )
            when = services.parse_datetime(taken_at)
            selected = await manual_supplies.selections(request, db)
        except (ValueError, TypeError) as exc:
            return reject_dose(str(exc))
        physical = BlendDose(
            id=next_blend_dose_id711(db),
            blend_id=blend.id, taken_at=when,
            volume_ml=draw["volume_ml"],
            entered_value=draw["entered_value"],
            entered_unit=draw["entered_unit"],
            kind="waste" if kind == "waste" else "dose",
            site=site.strip(), notes=notes.strip(),
        )
        db.add(physical)
        db.flush()
        manual_supplies.deduct(db, selected, blend_dose_id=physical.id)
        record(db, "blend", blend.id, "draw", after={
            "draw_id": physical.id, "kind": physical.kind,
            "volume_ml": physical.volume_ml, "taken_at": when.isoformat(),
            "site": physical.site, "entered_value": physical.entered_value,
            "entered_unit": physical.entered_unit,
            "supply_usage_count": len(selected),
        })
        if draw["volume_ml"] >= draw["remaining_before_ml"] - 1e-8:
            blend.status = "finished"
        if submission_token:
            idempotency.record(db, submission_token, "dose_create", digest)
        db.commit()
        if calendar_return:
            if request.headers.get("HX-Request", "").lower() == "true":
                return HTMLResponse("", headers={"HX-Redirect": calendar_return})
            return RedirectResponse(calendar_return, status_code=303)
        # Legacy BlendDose rows remain distinct from DoseLog; a completed
        # mixture draw appears exactly once in the combined timeline.
        if request.headers.get("HX-Request", "").lower() == "true":
            return HTMLResponse("", headers={
                "HX-Redirect": "/doses#dose-history-unified614"
            })
        return RedirectResponse("/doses#dose-history-unified614", status_code=303)

    vial = db.get(Vial, source_pk)
    if vial is None:
        return reject_dose("Choose a vial.")
    if planned_compound_id is not None and vial.compound_id != planned_compound_id:
        return reject_dose(
            "Selected vial belongs to a different compound than the calendar entry. "
            "Choose a vial for the planned compound."
        )
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
    if calendar_return:
        if request.headers.get("HX-Request", "").lower() == "true":
            return HTMLResponse("", headers={"HX-Redirect": calendar_return})
        return RedirectResponse(calendar_return, status_code=303)
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


# Release 711: correct the existing physical BlendDose, never constituent
# DoseLog records. The blend itself remains the immutable source identity.
def _blend_dose_snapshot711(draw: BlendDose, usages: list[SupplyUsage]) -> dict:
    supplies = {}
    for usage in usages:
        key = str(usage.supply_id)
        supplies[key] = supplies.get(key, 0) + usage.amount
    return {
        "blend_id": draw.blend_id,
        "taken_at": draw.taken_at.isoformat(),
        "volume_ml": draw.volume_ml,
        "entered_value": draw.entered_value,
        "entered_unit": draw.entered_unit,
        "kind": draw.kind,
        "site": draw.site or "",
        "notes": draw.notes or "",
        "supplies": supplies,
    }


def _blend_corrected_plan711(draw: BlendDose, value: float, unit: str) -> dict:
    """Calculate stock with this historical draw credited back first.

    Never transiently modify the attached ORM Blend or its historical draws;
    the 710 converter receives a read-only synthetic view of other draws.
    """
    from types import SimpleNamespace

    blend = draw.blend
    if blend.status not in ("in_use", "finished"):
        raise ValueError("This prepared blend is not eligible for correction.")
    other_draws = [row for row in blend.doses if row.id != draw.id]
    if sum(row.volume_ml for row in other_draws) > blend.final_volume_ml + 1e-8:
        raise ValueError("Other recorded draws exceed this blend's capacity.")
    view = SimpleNamespace(
        status="in_use", final_volume_ml=blend.final_volume_ml,
        components=blend.components, doses=other_draws,
    )
    return resolve_blend_draw710(view, value, unit)


@router.get("/doses/blends/{did}/edit")
def edit_blend_dose711(did: int, request: Request,
                       db: Session = Depends(get_scoped_db390)):
    draw = db.get(BlendDose, did)
    if draw is None:
        raise HTTPException(404, "Prepared-blend draw not found.")
    used_rows = list(db.scalars(
        select(SupplyUsage).where(SupplyUsage.blend_dose_id == did)
    ))
    used = _blend_dose_snapshot711(draw, used_rows)["supplies"]
    used_by_id = {int(sid): qty for sid, qty in used.items()}
    all_supplies = list(db.scalars(select(Supply).order_by(Supply.name, Supply.id)))
    counted_supply_kinds = set(db.scalars(
        select(SupplyCategory.key).where(SupplyCategory.unit == "count")
    ))
    dimensions = {row["dim"] for row in constituent_concentrations710(draw.blend)}
    # Multiple compounds must be entered in liquid volume; one compound
    # also permits its native mass or IU units.
    allowed = ["mL", "uL", "units"]
    if len({c.compound_id for c in draw.blend.components}) == 1 and len(dimensions) == 1:
        allowed = [u for u in U.WITHDRAW_UNITS if U.parse_unit(u).dim in dimensions | {"volume"}]
    return render(
        request, "blend_dose_edit711.html", dose=draw, blend=draw.blend,
        allowed_units=allowed, sites=INJECTION_SITES,
        used=used_by_id, supplies=_correction_available_supplies(all_supplies, used_by_id),
        counted_supply_kinds=counted_supply_kinds,
        history=list(db.scalars(
            select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend_dose",
                ChangeAudit.entity_id == did,
            ).order_by(ChangeAudit.id.desc())
        )),
        supply_names={str(s.id): s.name for s in all_supplies},
        correction_fields=(
            ("blend_id", "Physical blend"),
            ("taken_at", "Recorded time"),
            ("volume_ml", "Withdrawn volume (mL)"),
            ("entered_value", "Entered amount"),
            ("entered_unit", "Entered unit"),
            ("kind", "Type"),
            ("site", "Injection site"),
            ("notes", "Notes"),
            ("supplies", "Disposable usage"),
        ),
    )


@router.post("/doses/blends/{did}/edit")
async def update_blend_dose711(
    did: int, request: Request, taken_at: str = Form(""),
    amount: float = Form(...), unit: str = Form(...),
    kind: str = Form("dose"), site: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    if not reserve_inventory_write(db):
        raise HTTPException(409, "Inventory is busy. Please retry.")
    draw = db.get(BlendDose, did)
    if draw is None:
        db.rollback()
        raise HTTPException(404, "Prepared-blend draw not found.")
    back = f"/doses/blends/{did}/edit"
    try:
        if kind not in ("dose", "waste"):
            raise ValueError("Choose a valid administration or discard type.")
        if site and site not in INJECTION_SITES:
            raise ValueError("Unknown injection site.")
        when = services.parse_datetime(taken_at)
        plan = _blend_corrected_plan711(draw, amount, unit)
        used = list(db.scalars(select(SupplyUsage).where(
            SupplyUsage.blend_dose_id == did
        )))
        before = _blend_dose_snapshot711(draw, used)
        credits = {int(sid): qty for sid, qty in before["supplies"].items()}
        selected = await manual_supplies.selections(request, db, credits=credits)
        # All validation precedes any mutation; a failed correction leaves
        # the physical blend, usage rows, and audit history untouched.
        manual_supplies.restore_blend_dose(db, did)
        manual_supplies.deduct(db, selected, blend_dose_id=did)
        draw.volume_ml = plan["volume_ml"]
        draw.entered_value = plan["entered_value"]
        draw.entered_unit = plan["entered_unit"]
        draw.taken_at = when
        draw.kind = kind
        draw.site = site
        draw.notes = notes.strip()
        draw.blend.status = (
            "finished" if plan["remaining_after_ml"] <= 1e-8 else "in_use"
        )
        after = _blend_dose_snapshot711(
            draw, [SupplyUsage(supply_id=item.id, amount=qty)
                   for item, qty in selected],
        )
        record(db, "blend_dose", did, "edit", before=before, after=after)
        db.commit()
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    response = services.flash_redirect(
        "/doses", msg="Prepared-blend dose corrected.",
    )
    response.headers["location"] += "#dose-history-unified614"
    return response


@router.post("/doses/blends/{did}/delete")
def delete_blend_dose711(
    did: int, confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    require_inventory_write(db)
    draw = db.get(BlendDose, did)
    if draw is None:
        db.rollback()
        raise HTTPException(404, "Prepared-blend draw not found.")
    if confirm_delete != "yes":
        db.rollback()
        return services.flash_redirect(
            f"/doses/blends/{did}/edit",
            err="Confirm deletion before removing this recorded withdrawal.",
        )
    blend = draw.blend
    used = list(db.scalars(select(SupplyUsage).where(
        SupplyUsage.blend_dose_id == did
    )))
    before = _blend_dose_snapshot711(draw, used)
    # Calculate with the deleted draw excluded instead of relying on
    # relationship collection caching after an ORM delete.
    other_total = sum(row.volume_ml for row in blend.doses if row.id != did)
    manual_supplies.restore_blend_dose(db, did)
    record(db, "blend_dose", did, "delete", before=before, after={})
    db.delete(draw)
    if blend.status in ("in_use", "finished"):
        blend.status = (
            "finished" if blend.final_volume_ml - other_total <= 1e-8
            else "in_use"
        )
    db.commit()
    response = services.flash_redirect(
        "/doses", msg="Prepared-blend withdrawal deleted and inventory restored.",
    )
    response.headers["location"] += "#dose-history-unified614"
    return response
