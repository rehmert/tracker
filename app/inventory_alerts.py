"""Read-only inventory alerts derived from recorded inventory and historical use."""
from datetime import date
from sqlalchemy import select
from .models import Vial
from .forecasting import forecast_inventory


def collect_inventory_alerts(db, today: date | None = None, window_days: int = 90, horizon_days: int = 21):
    if not 1 <= horizon_days <= 365:
        raise ValueError("Alert horizon must be between 1 and 365 days")
    today = today or date.today()
    compounds, supplies = forecast_inventory(db, today=today, window_days=window_days)
    alerts = []
    for v in db.scalars(select(Vial)):
        if v.status not in ('sealed', 'in_use'):
            continue
        for kind, due in (('Expiration', v.expires_on), ('Beyond-use date', v.beyond_use_on)):
            if due is None:
                continue
            delta = (due - today).days
            if delta <= horizon_days:
                alerts.append(dict(level='critical' if delta < 0 else 'warning', category='Vial',
                                   name=f'{v.compound.name} · {v.label or "#" + str(v.id)}',
                                   reason=f'{kind} passed' if delta < 0 else f'{kind} in {delta} days',
                                   due=due, href=f'/vials/{v.id}', days=delta))
    for category, rows in (('Compound', compounds), ('Supply', supplies)):
        for row in rows:
            left = row['days_left']
            if left is None or left > horizon_days:
                continue
            alerts.append(dict(level='critical' if left <= 0 else 'warning', category=category,
                               name=row['name'], reason='Depleted' if left <= 0 else f'Estimated depletion in {left:.1f} days',
                               due=row['depletion'], href='/inventory-intelligence' if category == 'Compound' else '/supplies', days=left))
    alerts.sort(key=lambda x: (0 if x['level'] == 'critical' else 1, x['days'], x['category'], x['name'].casefold()))
    return alerts
