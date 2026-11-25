"""Read-only, server-resolved calendar quick-dose plan; no administration inferred."""
from datetime import date, datetime
from math import isfinite, isclose
from urllib.parse import urlencode

from sqlalchemy import select
from . import idempotency, services, units as U
from .blend_dose_unified710 import (
    constituent_concentrations710, resolve_blend_draw710,
)
from .models import Vial, Blend, ProtocolItem

_OPEN = ("due", "unrecorded")


def calendar_return786(day):
    return f"/calendar?month={day:%Y-%m}#calendar-day-{day.isoformat()}"


def manual_url786(event, day):
    return "/doses?" + urlencode(dict(
        compound_id=event["compound_id"], planned_date=day.isoformat(),
        planned_time=event.get("dose_time") or "",
        planned_amount=event["amount_value"], planned_unit=event["amount_unit"],
    ))


def parse_clock786(raw, day):
    text = raw.strip()
    if text.isascii() and text.isdigit() and len(text) in (3, 4):
        text = text.zfill(4)
        text = text[:2] + ":" + text[2:]
    if len(text) != 5 or text[2] != ":" or not (
            text[:2].isascii() and text[:2].isdigit() and
            text[3:].isascii() and text[3:].isdigit()):
        raise ValueError("Enter a 24-hour time, e.g. 0730 or 07:30.")
    try:
        when = datetime.fromisoformat(day.isoformat() + "T" + text)
    except ValueError:
        raise ValueError("Enter a valid 24-hour time.") from None
    if when > datetime.now():
        raise ValueError("The recorded administration time cannot be in the future.")
    return when


def quick_plan786(db, item_id, day):
    from .routers.calendar import _month_events
    if not 2000 <= day.year <= 2100:
        raise ValueError("Invalid calendar date.")
    _, _, events, _ = _month_events(day.replace(day=1), db)
    entries = events.get(day, [])
    matching = [e for e in entries if e.get("protocol_item_id") == item_id]
    if len(matching) != 1:
        raise ValueError("This scheduled dose is no longer available.")
    event = matching[0]
    plan = dict(event=event, day=day, manual_url=manual_url786(event, day),
                source=None, reason="", snapshot="")
    if day > date.today():
        plan["reason"] = "This date is in the future. Record an administration after it occurs."
        return plan
    if event["status"] not in _OPEN:
        plan["reason"] = "This dose is already recorded or requires reconciliation. Return to Calendar."
        plan["manual_url"] = ""
        return plan

    def unique_pending(cid):
        # Calendar's existing same-day matcher cannot identify which of several
        # occurrences a new log belongs to. Do not silently choose one.
        matches = [e for e in entries if e.get("compound_id") == cid
                   and e.get("protocol_item_id") is not None]
        if len(matches) == 1 and matches[0]["status"] in _OPEN:
            return matches[0]
        return None

    cid = event["compound_id"]
    if unique_pending(cid) is None:
        plan["reason"] = "Multiple same-day scheduled doses require the full dose log."
        return plan
    candidates = []
    amount, unit = event["amount_value"], event["amount_unit"]
    if not isfinite(amount) or amount <= 0:
        plan["reason"] = "The scheduled amount is invalid."
        return plan
    vials = list(db.scalars(select(Vial).where(
        Vial.compound_id == cid, Vial.status == "in_use").order_by(Vial.id)))
    views = services.vial_views(db, vials)
    for vial in vials:
        if (vial.closed_on or (vial.expires_on and vial.expires_on < day)
                or (vial.beyond_use_on and vial.beyond_use_on < day)
                or (vial.reconstituted_on and vial.reconstituted_on > day)
                or (vial.first_punctured_on and vial.first_punctured_on > day)
                or (vial.received_on and vial.received_on > day)):
            continue
        view = views[vial.id]
        try:
            base = U.amount_to_vial_base(amount, unit, view.dim, view.conc_per_ml)
            if (not isfinite(base) or not isfinite(view.remaining_base)
                    or not 0 < base <= view.remaining_base + 1e-7):
                continue
            if not view.conc_per_ml or not isfinite(view.conc_per_ml) or view.conc_per_ml <= 0:
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        candidates.append(dict(key=str(vial.id), label=f"{vial.label or 'Vial'} #{vial.id}",
                               amount=amount, unit=unit, details=[event["name"] + " · " + event["dose"]],
                               identity=[cid, base, view.conc_per_ml, item_id]))
    # For a mixed blend, only a single physical draw satisfying every
    # constituent's unrecorded same-time scheduled amount is eligible.
    blends = list(db.scalars(select(Blend).where(Blend.status == "in_use")))
    for blend in blends:
        if blend.created_at and blend.created_at.date() > day:
            continue
        try:
            components = constituent_concentrations710(blend)
            if cid not in {c["compound_id"] for c in components}:
                continue
            if len(components) == 1:
                draw = resolve_blend_draw710(blend, amount, unit)
                ids = [item_id]
                chosen_amount, chosen_unit = amount, unit
                detail = [event["name"] + " · " + event["dose"]]
            else:
                volumes, ids, detail = [], [], []
                for c in components:
                    scheduled = unique_pending(c["compound_id"])
                    if (scheduled is None or not event.get("dose_time")
                            or scheduled.get("dose_time") != event["dose_time"]):
                        raise ValueError("Unmatched blend constituent")
                    target, dim = U.to_base(scheduled["amount_value"], scheduled["amount_unit"])
                    if dim != c["dim"] or not isfinite(target) or target <= 0:
                        raise ValueError("Incompatible scheduled blend amount")
                    volumes.append(target / c["base_per_ml"])
                    ids.append(scheduled["protocol_item_id"])
                    detail.append(scheduled["name"] + " · " + scheduled["dose"])
                if not all(isclose(v, volumes[0], rel_tol=1e-9, abs_tol=1e-10) for v in volumes):
                    continue
                chosen_amount, chosen_unit = volumes[0], "mL"
                draw = resolve_blend_draw710(blend, chosen_amount, chosen_unit)
            candidates.append(dict(key=f"blend:{blend.id}", label=f"{blend.label} #{blend.id}",
                                   amount=chosen_amount, unit=chosen_unit, details=detail,
                                   identity=[ids, [(c["compound_id"], c["amount_base"],
                                                   c["base_per_ml"]) for c in draw["components"]]]))
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            continue
    if len(candidates) != 1:
        plan["reason"] = ("No eligible in-use vial or blend matches this scheduled dose."
                          if not candidates else "Multiple eligible in-use sources; select the actual source in the full dose log.")
        return plan
    source = candidates[0]
    plan["source"] = source
    plan["snapshot"] = idempotency.payload_hash([
        item_id, day.isoformat(), event.get("dose_time"), event["amount_value"],
        event["amount_unit"], source["key"], source["amount"], source["unit"],
        source["identity"], source["details"], source["label"],
    ])
    return plan
