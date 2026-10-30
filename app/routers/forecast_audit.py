"""Read-only shared-stock and demand-quality audit for average-rate forecasts."""
import csv
import io
import math
from collections import defaultdict
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..templating import render
from .inventory_forecast import build_rows

router = APIRouter()

def audit_rows(db, days=28):
    # Existing forecast owns conversions, vial eligibility and usage accounting.
    source = build_rows(db, days=days)
    groups = defaultdict(list)
    for row in source:
        groups[(str(row['compound']), str(row['unit']))].append(row)

    output = []
    for (compound, unit), items in groups.items():
        # The same stock pool appears once per protocol item in build_rows.
        # Never sum those repeated available quantities.
        values = [float(r['available']) for r in items]
        vials = [int(r['vials']) for r in items]
        consistent = (
            all(math.isfinite(v) and v >= 0 for v in values)
            and len({round(v, 8) for v in values}) == 1
            and len(set(vials)) == 1
        )
        unknown = any(r['demand'] is None or not math.isfinite(float(r['demand']))
                      or float(r['demand']) < 0 for r in items)
        # If rows disagree about stock, the shared-stock calculation is
        # not safe to aggregate. Report uncertainty, not a false shortage.
        available = values[0] if consistent else None
        demand = None if unknown else sum(float(r['demand']) for r in items)
        if not consistent:
            flag = 'Review stock mismatch'
        elif unknown:
            flag = 'Demand not estimable'
        elif not vials[0]:
            flag = 'No eligible vials'
        elif demand > available:
            flag = 'Potential shortfall'
        else:
            flag = 'Roughly covered'
        output.append({
            'compound': compound,
            'unit': unit,
            'protocols': len({r['protocol_id'] for r in items}),
            'items': len(items),
            'vials': vials[0] if consistent else None,
            'available': available,
            'demand': demand,
            'flag': flag,
        })
    return sorted(output, key=lambda r: (r['flag'] == 'Roughly covered', r['compound'].casefold(), r['unit']))

@router.get('/forecast-audit')
def forecast_audit(request: Request, db: Session = Depends(get_db)):
    return render(request, 'forecast_audit.html', rows=audit_rows(db), days=28)

@router.get('/forecast-audit.csv')
def forecast_audit_csv(db: Session = Depends(get_db)):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['Compound', 'Unit', 'Active protocols', 'Protocol items',
                     'Eligible vials', 'Shared stock (approx)', 'Combined 28d demand (approx)', 'Flag'])
    for row in audit_rows(db):
        name = row['compound']
        if name.lstrip().startswith(('=', '+', '-', '@')):
            name = "'" + name
        writer.writerow([name, row['unit'], row['protocols'], row['items'],
                         '' if row['vials'] is None else row['vials'],
                         '' if row['available'] is None else round(row['available'], 4),
                         '' if row['demand'] is None else round(row['demand'], 4),
                         row['flag']])
    # A UTF-8 BOM improves spreadsheet interoperability.
    value = stream.getvalue()
    return Response('\ufeff' + value, media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="forecast-audit.csv"'})
