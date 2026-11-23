"""Read-only, approximate inventory planning (not dosing guidance)."""
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
import csv
import io
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..scoped_db390 import get_scoped_db390
from ..models import Protocol, Compound, Vial
from ..services import vial_views
from .. import units as U
from ..templating import render

router = APIRouter()

# Quantities use base units: mcg for mass, IU for potency, mL for
# withdrawals. Volume requirements are comparable only when every
# included vial has a known recorded concentration.
def normalized(value, unit):
    if unit not in U.DOSE_UNITS:
        return None
    try:
        amount, _ = U.to_base(float(value), unit)
        return amount if isfinite(amount) and amount >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def compatible(a, b):
    try:
        vial_unit, plan_unit = U.parse_unit(a), U.parse_unit(b)
    except (ValueError, TypeError):
        return False
    return (vial_unit.dim == plan_unit.dim or
            (plan_unit.dim == "volume" and vial_unit.dim in ("mass", "iu")))


def weekly(item):
    """A protocol interval is one dose every freq_count days."""
    try:
        count = float(item.freq_count)
        dose = normalized(item.amount_value, item.amount_unit)
        if dose is None or not isfinite(count) or count <= 0 or dose <= 0:
            return None
        if item.freq_period == "interval":
            result = dose * 7.0 / count
        else:
            periods = {"day": 7.0, "week": 1.0,
                       "month": 7.0 / (365.2425 / 12.0)}
            if item.freq_period not in periods:
                return None
            result = dose * count * periods[item.freq_period]
        return result if isfinite(result) and result > 0 else None
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return None


def _same_concentration(a, b):
    dim_a, conc_a = a
    dim_b, conc_b = b
    return (dim_a == dim_b and
            abs(conc_a - conc_b) <= max(conc_a, conc_b) * 1e-6)


def build_rows(db, days=28):
    today = date.today()
    protocols = db.scalars(select(Protocol).where(Protocol.is_active.is_(True))).all()
    compounds = {c.id: c for c in db.scalars(select(Compound)).all()}
    vials = db.scalars(select(Vial)).all()
    # Canonical inventory views respect approved COA values, logged
    # doses/waste and blend transfers. Never subtract usage twice.
    views = vial_views(db, vials)
    rows = []
    for p in protocols:
        if p.start_date and p.start_date > today + timedelta(days=days):
            continue
        if p.end_date and p.end_date < today:
            continue
        for item in p.items:
            compound = compounds.get(item.compound_id)
            try:
                plan_unit = U.parse_unit(item.amount_unit)
            except (TypeError, ValueError):
                plan_unit = None
            volume_plan = plan_unit is not None and plan_unit.dim == "volume"
            available = 0.0
            count = 0
            excluded = 0
            missing_concentration = 0
            strengths = []
            for vial in vials:
                if vial.compound_id != item.compound_id:
                    continue
                if vial.status not in ("sealed", "in_use") or vial.closed_on:
                    excluded += 1
                    continue
                if ((vial.expires_on and vial.expires_on < today) or
                        (vial.beyond_use_on and vial.beyond_use_on < today)):
                    excluded += 1
                    continue
                view = views.get(vial.id)
                if (view is None or plan_unit is None or
                        not compatible(vial.content_unit, item.amount_unit) or
                        not isfinite(view.remaining_base) or
                        not isfinite(view.content_base) or
                        view.content_base <= 0):
                    excluded += 1
                    continue
                if volume_plan:
                    concentration = view.conc_per_ml
                    if (concentration is None or not isfinite(concentration)
                            or concentration <= 0):
                        missing_concentration += 1
                        excluded += 1
                        continue
                    liquid_remaining = view.remaining_base / concentration
                    if not isfinite(liquid_remaining) or liquid_remaining < 0:
                        missing_concentration += 1
                        excluded += 1
                        continue
                    available += liquid_remaining
                    strengths.append((view.dim, concentration))
                else:
                    available += view.remaining_base
                count += 1

            rate = weekly(item)
            mixed = (volume_plan and len(strengths) > 1
                     and any(not _same_concentration(strengths[0], val)
                             for val in strengths[1:]))
            unknown_volume = bool(volume_plan and missing_concentration and count == 0)
            display_available = None if unknown_volume else available
            demand = rate * days / 7.0 if rate is not None else None
            weeks = None
            if rate is None:
                status = "Not estimable"
            elif unknown_volume:
                status = "Concentration unavailable"
            elif volume_plan and missing_concentration:
                status = "Volume data incomplete"
            elif mixed:
                # Physical mL remain summable even when mass per withdrawal
                # differs. Preserve the warning, but show volume-based days.
                weeks = available / rate
                status = "Mixed concentrations - review"
            else:
                weeks = available / rate
                status = ("No matching inventory" if count == 0 else
                          "Below rough demand" if available < demand else
                          "Roughly covered")

            if volume_plan:
                unit, scale = "mL", 1.0
            elif plan_unit is not None and plan_unit.dim == "iu":
                unit, scale = "IU", 1.0
            else:
                unit, scale = "mg", 1000.0

            caveat = ("Average only; ignores schedule windows, escalation, "
                      "exclusions and future expiration.")
            if mixed:
                caveat += (" Recorded vial concentrations differ; displayed "
                           "volume is physical liquid only and is not "
                           "interchangeable dosing capacity.")
            if missing_concentration:
                caveat += (" Some matching vials have no usable recorded "
                           "liquid volume/concentration; total coverage "
                           "cannot be reliably calculated.")
            rows.append(dict(
                protocol=p.name,
                compound=compound.name if compound else
                    f"Compound #{item.compound_id}",
                unit=unit, vials=count, excluded=excluded,
                available=(display_available / scale
                           if display_available is not None else None),
                demand=demand / scale if demand is not None else None,
                weeks=weeks, status=status, protocol_id=p.id,
                caveat=caveat))
    return sorted(rows, key=lambda r: (
        r["status"] != "No matching inventory",
        r["status"] != "Below rough demand",
        r["compound"].lower(), r["protocol"].lower()))


@router.get('/inventory-forecast')
def inventory_forecast(request:Request, db:Session=Depends(get_scoped_db390)):
    return render(request,'inventory_forecast.html',rows=build_rows(db),horizon=28)

@router.get('/inventory-forecast.csv')
def inventory_forecast_csv(db:Session=Depends(get_scoped_db390)):
    buffer=io.StringIO(); writer=csv.writer(buffer)
    writer.writerow(['Protocol','Compound','Eligible vials','Excluded vials','Remaining (approx)','28-day demand (approx)','Unit','Weeks at average rate','Status','Caveat'])
    for r in build_rows(db):
        writer.writerow([r['protocol'],r['compound'],r['vials'],r['excluded'],'' if r['available'] is None else round(r['available'],4),
            '' if r['demand'] is None else round(r['demand'],4),r['unit'],
            '' if r['weeks'] is None else round(r['weeks'],2),r['status'],r['caveat']])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="inventory-forecast.csv"'})
