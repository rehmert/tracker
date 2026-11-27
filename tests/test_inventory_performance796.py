from datetime import date, timedelta
import random

import pytest
from app.routers.fefo_forecast import simulate_fefo
from app.routers import planning_hub, planning_priorities

def reference_simulate(stock, events, today, horizon_days):
    """
    Pure-Python FEFO simulation.

    Stock:
        id, remaining, expiry

    Events:
        date, amount

    Inventory with unknown expiry is not included.

    An expiry date is treated conservatively: stock is
    removed before demand scheduled on that date.

    Does not change database records.
    """

    end = today + timedelta(days=horizon_days)

    vials = [
        {
            "id": row["id"],
            "remaining": float(row["remaining"]),
            "expiry": row["expiry"],
        }
        for row in stock
        if row["remaining"] > 0
        and row["expiry"] is not None
        and row["expiry"] >= today
    ]

    vials.sort(key=lambda x: (x["expiry"], x["id"]))

    scheduled = sorted(
        [
            (when, float(amount))
            for when, amount in events
            if today <= when < end
        ],
        key=lambda x: x[0],
    )

    consumed = 0.0
    shortage = 0.0
    expired = 0.0
    first_shortage = None

    def expire_through(day):
        nonlocal expired

        for vial in vials:
            if vial["expiry"] <= day and vial["remaining"] > 0:
                expired += vial["remaining"]
                vial["remaining"] = 0.0

    for when, amount in scheduled:
        expire_through(when)

        needed = amount

        for vial in vials:
            if needed <= 0:
                break

            if vial["remaining"] <= 0:
                continue

            taken = min(vial["remaining"], needed)

            vial["remaining"] -= taken
            needed -= taken
            consumed += taken

        if needed > 1e-9:
            shortage += needed
            if first_shortage is None:
                first_shortage = when

    # Remove inventory expiring before the end of the horizon.
    # The horizon's final day is not itself simulated.
    expire_through(end - timedelta(days=1))

    remaining = sum(v["remaining"] for v in vials)

    return {
        "demand": sum(amount for _, amount in scheduled),
        "consumed": consumed,
        "shortage": shortage,
        "expired": expired,
        "remaining": remaining,
        "first_shortage": first_shortage,
        "events": len(scheduled),
    }



@pytest.mark.parametrize("seed", range(20))
def test_fefo_matches_previous_algorithm(seed):
    rng = random.Random(seed)
    today = date(2026, 1, 1)
    stock = [{"id": i, "remaining": rng.randint(0, 100)/7,
              "expiry": today + timedelta(days=rng.randint(-5, 65))}
             for i in range(80)]
    stock.append({"id": 81, "remaining": 10, "expiry": None})
    events = [(today + timedelta(days=rng.randint(-2, 65)),
               rng.randint(0, 100)/9) for _ in range(120)]
    for horizon in (7, 14, 28, 56):
        assert simulate_fefo(stock, events, today, horizon) == reference_simulate(stock, events, today, horizon)


def test_default_planning_calculates_priorities_once(monkeypatch):
    calls = []
    original = planning_priorities.priority_rows
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(planning_priorities, "priority_rows", counted)
    monkeypatch.setattr(planning_hub, "build_fefo", lambda db: ([], []))
    monkeypatch.setattr(planning_hub, "render", lambda request, template, **kwargs: kwargs)
    result = planning_hub.planning_hub(None, None, 28, "", "all", "priorities")
    assert len(calls) == 1
    assert result["rows"] == []
    assert result["totals"]["shortages"] == 0
