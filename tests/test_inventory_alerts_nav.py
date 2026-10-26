from datetime import date
from pathlib import Path
from app.inventory_alerts import collect_inventory_alerts


def test_alerts_reject_bad_horizon():
    try:
        collect_inventory_alerts(None, horizon_days=0)
    except ValueError:
        pass
    else:
        assert False


def test_nav_controls_and_storage():
    base = (Path(__file__).parents[1] / 'app/templates/base.html').read_text()
    js = (Path(__file__).parents[1] / 'app/static/nav_sort.js').read_text()
    assert 'nav-sort-mode' in base and 'nav-sortable' in base
    assert 'tracker-nav-order-v1' in js and 'localStorage' in js
    assert '/inventory-alerts' in base
