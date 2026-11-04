from datetime import date, datetime
from pathlib import Path
from app.pk_inventory_events import allocate_events


def test_vial_allocation_is_reconciled():
    stock = [{
        'id':3,
        'remaining_mg':5,
        'expires_on':None,
        'beyond_use_on':None,
        'closed_on':None,
        'status':'sealed',
    }]

    result = allocate_events(
        stock,
        [(datetime(2026,11,5,8),3)],
        date(2026,11,4),
        date(2026,12,4),
    )

    assert result['forecast_events'][0][
        'vial_allocations'
    ][0]['vial_id'] == 3

    assert result['vial_balances'][0]['remaining_mg'] == 2
    assert stock[0]['remaining_mg'] == 5


def test_nominal_metadata_ui():
    html = Path(
        'app/templates/protocol_edit.html'
    ).read_text()
    assert 'tracker-pk-vials100.js?v=bundle100' in html
