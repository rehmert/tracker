from datetime import date
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Purchase, Supply, SupplyUsage
from app.routers.purchases import parse_bulk, add_purchase_supply, edit_purchase_supply
from app.services import supply_line_cents, purchase_landed
from app.migrations import migrate
from app.supply_categories import ensure_categories


def test_bulk_pack_pricing_and_consumption(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_categories(db)
        p = Purchase(vendor='Test', purchased_on=date(2026, 10, 26))
        db.add(p); db.commit()
        monkeypatch.setattr('app.routers.purchases.services.flash_redirect', lambda url, **kw: (url, kw))
        url, result = add_purchase_supply(p.id, '29G needle', 'needle', 1, '0', '', '', db, '2', '100', '17.99')
        assert 'msg' in result
        s = db.query(Supply).one()
        assert s.purchased_qty == s.remaining_qty == 200
        assert s.bulk_pack_count == 2 and s.bulk_units_per_pack == 100
        assert supply_line_cents(s) == 1799
        assert purchase_landed(p)[-s.id] == 1799
        s.remaining_qty -= 3
        db.add(SupplyUsage(supply_id=s.id, amount=3)); db.commit()
        assert s.remaining_qty == 197
        url, result = edit_purchase_supply(p.id, s.id, s.name, s.kind, 1, '0', '', '', db, '3', '100', '26.99')
        assert 'msg' in result
        assert s.purchased_qty == 300 and s.remaining_qty == 297
        assert supply_line_cents(s) == 2699
        migrate(engine)
        assert {'bulk_pack_count','bulk_units_per_pack','bulk_total_cents'} <= {x['name'] for x in inspect(engine).get_columns('supplies')}


def test_bulk_validation():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_categories(db)
        assert parse_bulk(db, 'needle', 1, '1', '50', '5.99') == (50, 1, 50.0, 599)
        import pytest
        with pytest.raises(ValueError):
            parse_bulk(db, 'needle', 1, '1', '12.5', '4.00')
        with pytest.raises(ValueError):
            parse_bulk(db, 'needle', 1, '2', '', '4.00')
