from datetime import date, datetime, timedelta
from app.pk_inventory_events import allocate_events
from app.pk_release_quality import reconcile


def vial(q, expiry=None):
    return dict(
        remaining_mg=q,
        expires_on=expiry,
        beyond_use_on=None,
        closed_on=None,
        status="sealed",
    )


def test_expired_physical_stock_is_not_usable_stock():
    r = allocate_events(
        [vial(10, date(2026, 11, 5))],
        [],
        date(2026, 11, 4),
        date(2026, 12, 4),
    )
    assert r["remaining_after_allocation_mg"] == 10
    assert r["remaining_usable_at_horizon_mg"] == 0
    assert r["remaining_expired_at_horizon_mg"] == 10


def test_full_ledger_reconciliation_beyond_display_limit():
    t = datetime(2026, 11, 4, 8)
    events = [
        (t + timedelta(hours=i), 1)
        for i in range(1050)
    ]
    r = allocate_events(
        [vial(1200)], events,
        date(2026, 11, 4),
        date(2027, 1, 4),
    )
    assert (r["event_count"], len(r["forecast_events"])) == (
        1050, 1000
    )
    assert r["total_allocated_mg"] == 1050
    assert r["demand_reconciled"]
    assert r["forecast_truncated"]


def test_compound_wide_reconciliation():
    t = datetime(2026, 11, 4, 8)
    r = reconcile(
        [(t, 5)],
        [(t, 4), (t + timedelta(hours=2), 1)],
        t.date(), t.date(),
    )
    assert r["recorded_count"] == 2
    assert r["planned_count"] == 1
    assert r["recorded_mg"] == 5
