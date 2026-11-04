"""Exact-time, read-only PK experiment scheduling and statistics."""
from datetime import datetime, time, timedelta
from math import isfinite

UNITS = {"mg": 1.0, "mcg": 0.001, "g": 1000.0}
PERIODS = {
    "day": 1.0,
    "week": 7.0,
    "month": 365.2425 / 12,
}


def schedule_doses(
    protocol, compound_id, anchor_date, days,
    dose_multiplier=1.0, interval_multiplier=1.0,
):
    if not 0 < days <= 730:
        raise ValueError("Invalid schedule horizon")
    start = datetime.combine(anchor_date, time.min)
    stop = start + timedelta(days=days)
    doses = []

    for item in protocol.items:
        if item.compound_id != compound_id:
            continue

        factor = UNITS.get(item.amount_unit)
        if factor is None:
            raise ValueError(
                "Selected compound includes non-mass units"
            )
        amount = float(item.amount_value) * factor * dose_multiplier
        if not isfinite(amount) or amount <= 0:
            raise ValueError("Invalid modeled dose")

        count = float(item.freq_count)
        if not isfinite(count) or count <= 0:
            raise ValueError("Invalid saved frequency")
        if not isfinite(interval_multiplier) or interval_multiplier <= 0:
            raise ValueError("Invalid interval multiplier")

        if item.freq_period == "interval":
            interval = count * interval_multiplier
        else:
            period = PERIODS.get(item.freq_period)
            if period is None:
                raise ValueError("Unsupported frequency period")
            interval = period / count * interval_multiplier

        if interval < 1 / 24:
            raise ValueError("Intervals below one hour are unsupported")

        dose_time = item.dose_time or "00:00"
        try:
            hour, minute = map(int, dose_time.split(":"))
            origin = datetime.combine(
                anchor_date, time(hour, minute)
            )
        except (TypeError, ValueError):
            raise ValueError("Invalid administration time")

        week_start = max(1, item.start_week or 1)
        stage_start = start + timedelta(
            days=7 * (week_start - 1)
        )
        stage_end = (
            start + timedelta(days=7 * item.end_week)
            if item.end_week is not None
            else stop
        )
        stage_end = min(stage_end, stop)

        if stage_start >= stage_end:
            continue

        weekdays = item.dose_days or ""
        if weekdays:
            if interval_multiplier != 1:
                raise ValueError(
                    "Interval adjustments are unavailable for "
                    "fixed-weekday schedules"
                )
            try:
                selected = {
                    int(v) for v in weekdays.split(",")
                    if v.strip()
                }
            except ValueError:
                raise ValueError("Invalid weekdays")
            if not selected or not selected <= set(range(7)):
                raise ValueError("Invalid weekdays")

            for offset in range(days):
                candidate = origin + timedelta(days=offset)
                if (
                    candidate.weekday() in selected
                    and stage_start <= candidate < stage_end
                ):
                    doses.append((candidate, amount))
        else:
            for index in range(10001):
                candidate = origin + timedelta(
                    days=index * interval
                )
                if candidate >= stop:
                    break
                if stage_start <= candidate < stage_end:
                    doses.append((candidate, amount))
            else:
                raise ValueError(
                    "Schedule exceeds safe iteration limit"
                )

        if len(doses) > 1000:
            raise ValueError(
                "Experiment exceeds 1,000 modeled doses"
            )

    return sorted(doses, key=lambda row: row[0])


def interval_assessment(rows, doses):
    """Compare completed equal-dose maintenance intervals.

    Stability means neighboring modeled interval means differ
    by <=5%; this is not an established clinical steady state.
    """
    result = {
        "status": "Not assessable",
        "interval_change_percent": None,
        "accumulation_ratio": None,
    }
    if len(rows) < 2 or len(doses) < 5:
        return result

    last = sorted(doses)[-5:]
    gaps = [
        (last[i + 1][0] - last[i][0]).total_seconds()
        for i in range(4)
    ]
    if min(gaps) <= 0 or any(
        abs(g - gaps[0]) > 3600 for g in gaps
    ):
        return result

    if any(
        abs(d[1] - last[0][1]) >
        max(0.000001, last[0][1] * 0.001)
        for d in last
    ):
        return result

    samples = [
        (datetime.fromisoformat(row["at"]), row["planned"])
        for row in rows
    ]

    def mean_between(first, second):
        points = []
        for (a, va), (b, vb) in zip(samples, samples[1:]):
            if b <= first or a >= second:
                continue
            lo, hi = max(a, first), min(b, second)
            span = (b - a).total_seconds()
            if span <= 0:
                continue
            vl = va + (vb - va) * (
                (lo - a).total_seconds() / span
            )
            vr = va + (vb - va) * (
                (hi - a).total_seconds() / span
            )
            points.append((
                (hi - lo).total_seconds(),
                (vl + vr) / 2,
            ))
        total = sum(seconds for seconds, _ in points)
        if total < (second - first).total_seconds() * 0.98:
            return None
        return (
            sum(seconds * value for seconds, value in points)
            / total if total else None
        )

    early = mean_between(last[0][0], last[1][0])
    older = mean_between(last[2][0], last[3][0])
    newer = mean_between(last[3][0], last[4][0])

    if older is None or newer is None or older <= 0:
        return result

    change = 100 * (newer - older) / older
    result["interval_change_percent"] = round(change, 3)
    result["accumulation_ratio"] = (
        round(newer / early, 4)
        if early is not None and early > 0 else None
    )
    result["status"] = (
        "Modeled intervals within 5%"
        if abs(change) <= 5
        else "Model still accumulating or changing"
    )
    return result
