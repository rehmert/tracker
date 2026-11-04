"""Read-only companion diagnostics for PK workbench."""
from datetime import date, datetime, timedelta
from sqlalchemy import select
from .calendar import staged_occurrences
from .models import DoseLog, Vial


def timing_check(protocol, compound_id, start, days):
    from .pk_precision import schedule_doses
    issues = []
    compared = 0

    for item in protocol.items:
        if item.compound_id != compound_id:
            continue

        if (
            not item.dose_days
            and item.freq_period == "interval"
            and item.freq_count < 1
        ):
            issues.append(
                "Calendar is date-granular and can collapse "
                "sub-day administrations"
            )
            continue

        planned = {
            d.isoformat()
            for d in staged_occurrences(item, start, days)
        }
        isolated = type(
            "Schedule", (), {"items": [item]}
        )()
        precise = {
            t.date().isoformat()
            for t, _ in schedule_doses(
                isolated, compound_id, start, days
            )
        }
        compared += 1
        if planned != precise:
            issues.append(
                "Calendar/PK date disagreement for stage "
                + str(item.start_week)
            )

    return {
        "checked_stages": compared,
        "warnings": list(dict.fromkeys(issues)),
        "calendar_unchanged": True,
    }


def recorded(db, compound_id, first, last):
    lo = datetime.combine(first, datetime.min.time())
    hi = datetime.combine(
        last + timedelta(days=1), datetime.min.time()
    )
    result = db.execute(
        select(DoseLog.taken_at, DoseLog.amount_base)
        .join(Vial, DoseLog.vial_id == Vial.id)
        .where(
            Vial.compound_id == compound_id,
            DoseLog.kind == "dose",
            DoseLog.taken_at >= lo,
            DoseLog.taken_at < hi,
        )
        .order_by(DoseLog.taken_at)
    ).all()

    return [
        (at, float(amount) / 1000)
        for at, amount in result
    ]


def reconcile(baseline, actual, first, last):
    planned = [
        (at, mg) for at, mg in baseline
        if first <= at.date() <= last
    ]
    observed = [
        (at, mg) for at, mg in actual
        if first <= at.date() <= last
    ]

    return {
        "from": first.isoformat(),
        "through": last.isoformat(),
        "planned_count": len(planned),
        "recorded_count": len(observed),
        "planned_mg": round(
            sum(mg for _, mg in planned), 5
        ),
        "recorded_mg": round(
            sum(mg for _, mg in observed), 5
        ),
        "scope": (
            "Compound-wide logged doses; "
            "protocol attribution is unavailable"
        ),
    }
