"""Release 762 measurement-only, deterministic longitudinal calculations.

No clinical diagnosis, synthetic body-fat calculation or unmeasured interpolation.
Weight averages use one actual reading per calendar date; both window coverage
and duration are explicit. Strength comparisons require one machine and exact reps.
"""
from datetime import datetime, date, time, timedelta
from math import isfinite
from statistics import mean

def daily_weights762(rows):
    # Rows supplied chronologically: last same-day reading wins.
    observed = {}
    for row in sorted(rows, key=lambda r: (r.measured_at, r.id or 0)):
        if row.weight_kg is not None and isfinite(row.weight_kg):
            observed[row.measured_at.date()] = float(row.weight_kg)
    return sorted(observed.items())

def moving762(observed, days, *, min_samples=1):
    result = []
    for day, _ in observed:
        values = [v for d, v in observed if day - timedelta(days=days - 1) <= d <= day]
        if len(values) >= min_samples:
            result.append((datetime.combine(day, time(12)), mean(values), len(values)))
    return result

def interval_average762(observed, end, days, offset=0):
    finish = end - timedelta(days=offset)
    start = finish - timedelta(days=days - 1)
    samples = [v for d, v in observed if start <= d <= finish]
    return (mean(samples), len(samples)) if samples else (None, 0)

def period_change762(observed, end, days, min_count):
    current, n = interval_average762(observed, end, days)
    previous, prev_n = interval_average762(observed, end, days, days)
    if current is None or previous is None or n < min_count or prev_n < min_count:
        return None
    return current - previous

def metric_change_details762(rows, attr):
    """Compare observations on distinct dates only, last reading per date."""
    distinct = {}
    for row in rows:
        value = getattr(row, attr)
        if value is not None:
            distinct[row.measured_on] = float(value)
    if len(distinct) < 2:
        return None
    first, last = min(distinct), max(distinct)
    return {"delta": distinct[last] - distinct[first],
            "first": first, "last": last, "days": len(distinct)}


def metric_change762(rows, attr):
    details = metric_change_details762(rows, attr)
    return details["delta"] if details else None

def weight_report762(observed, today, initial=None, goal=None):
    latest = observed[-1][1] if observed else None
    first = float(initial) if initial is not None else (observed[0][1] if observed else None)
    avg7, n7 = interval_average762(observed, today, 7)
    avg28, n28 = interval_average762(observed, today, 28)
    d7 = period_change762(observed, today, 7, 3)
    d28 = period_change762(observed, today, 28, 7)
    lost = first - latest if first is not None and latest is not None else None
    remaining = latest - goal if latest is not None and goal is not None else None
    pct_lost = 100 * lost / first if lost is not None and first > 0 else None
    denominator = first - goal if first is not None and goal is not None else None
    goal_pct = 100 * lost / denominator if denominator is not None and denominator > 0 and lost is not None else None
    # A plateau requires 4 weeks with adequate weekly coverage AND a minimal
    # change in the fitted 28-day observations. This is descriptive, not diagnostic.
    recent = [(d, v) for d, v in observed if today - timedelta(days=27) <= d <= today]
    weeks = [
        [v for d, v in recent if today - timedelta(days=(7*i+6)) <= d <= today-timedelta(days=7*i)]
        for i in range(4)
    ]
    plateau = None
    if latest is not None and all(len(x) >= 3 for x in weeks):
        plateau = abs(mean(weeks[0])-mean(weeks[3])) < 0.005 * latest
    return {
        "latest": latest, "first": first, "lost": lost, "remaining": remaining,
        "pct_lost": pct_lost, "goal_pct": goal_pct,
        "avg7": avg7, "avg28": avg28, "n7": n7, "n28": n28,
        "d7": d7, "d28": d28, "plateau": plateau,
        "latest_date": observed[-1][0] if observed else None,
    }

def strength_sessions762(rows):
    """Rows: (session date, machine ID, reps, weight); compare exact same reps."""
    grouped = {}
    for day, machine_id, reps, weight in rows:
        if not isfinite(float(weight)) or reps < 1:
            continue
        key = (machine_id, reps, day)
        grouped[key] = max(grouped.get(key, 0), float(weight))
    return grouped

def strength_trend762(rows, equipment_id, reps):
    grouped = strength_sessions762(rows)
    pairs = sorted((d, load) for (mid, r, d), load in grouped.items()
                   if mid == equipment_id and r == reps)
    if len(pairs) < 2:
        return pairs, "Not enough comparable sets"
    first, last = pairs[0][1], pairs[-1][1]
    if last > first + 0.5:
        verdict = "Improving"
    elif last < first - 0.5:
        verdict = "Declining"
    else:
        verdict = "Stable"
    return pairs, verdict

def interpret762(weight, waist_change, strength):
    """Explain the independent observations; never claim confirmed fat/muscle gain."""
    weight_change = weight.get("d28")
    if weight_change is None:
        weight_label = "Insufficient 28-day weight coverage"
    elif weight_change < -0.005 * (weight.get("latest") or 1):
        weight_label = "28-day weight average is decreasing"
    elif weight_change > 0.005 * (weight.get("latest") or 1):
        weight_label = "28-day weight average is increasing"
    else:
        weight_label = "28-day weight average is broadly stable"
    if waist_change is None:
        waist_label = "Waist trend unavailable"
    elif waist_change < -0.5:
        waist_label = "Recorded waist circumference is smaller"
    elif waist_change > 0.5:
        waist_label = "Recorded waist circumference is larger"
    else:
        waist_label = "Recorded waist circumference is similar"
    strength_label = "Comparable machine strength: " + strength.lower()
    if weight_change is not None and weight_change < 0 and waist_change is not None and waist_change < 0 and strength == "Improving":
        headline = "Weight and waist are decreasing while matched-set performance improves."
    elif weight_change is not None and abs(weight_change) < 0.005 * (weight.get("latest") or 1) and waist_change is not None and waist_change < 0 and strength == "Improving":
        headline = "Possible body recomposition; body-fat and muscle change are not confirmed."
    elif weight_change is not None and weight_change < 0 and strength == "Declining":
        headline = "Weight is decreasing while matched-set performance declines; review training, nutrition and recovery records."
    elif weight.get("plateau") and (waist_change is None or abs(waist_change) <= 0.5):
        headline = "Possible sustained scale-weight plateau; more waist measurements may help interpret it."
    else:
        headline = "Use weight, waist and exercise trends together; current evidence is not definitive."
    return {"headline": headline, "evidence": (weight_label, waist_label, strength_label)}
