from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Purchase, Supply, Vial, Compound
from app import services
from app.routers.purchases import add_purchase_supply, delete_purchase


def test_mixed_order_allocation_and_purchase_guard(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Compound(name='Example')
        p = Purchase(vendor='Shared Vendor', purchased_on=date(2026, 10, 26),
                     shipping_cents=1500, tax_cents=500, discount_cents=0)
        db.add_all([c, p]); db.flush()
        db.add(Vial(compound_id=c.id, purchase_id=p.id, content_value=10,
                    content_unit='mg', unit_price_cents=10000))
        db.commit()
        monkeypatch.setattr('app.routers.purchases.services.flash_redirect', lambda url, **kw: (url, kw))
        url, msg = add_purchase_supply(p.id, 'Pill pack', 'pill', 20.0, '2.50', str(c.id), '', db)
        assert url == f'/purchases/{p.id}'
        assert 'added' in msg['msg'].lower()
        db.expire_all()
        p = db.get(Purchase, p.id)
        assert len(p.supplies) == 1 and p.supplies[0].remaining_qty == 20
        landed = services.purchase_landed(p)
        assert len(landed) == 2
        assert round(sum(landed.values())) == 10000 + 20 * 250 + 2000
        assert round(landed[next(iter(landed))]) == 11333
        assert delete_purchase(p.id, db)[1].get('err')
        assert db.get(Purchase, p.id) is not None


def test_pill_quantities_must_be_whole(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        p = Purchase(vendor='Shared Vendor', purchased_on=date(2026, 10, 26))
        db.add(p); db.commit()
        monkeypatch.setattr('app.routers.purchases.services.flash_redirect', lambda url, **kw: (url, kw))
        result = add_purchase_supply(p.id, 'Pill pack', 'pill', 1.5, '1', '', '', db)
        assert 'whole number' in result[1]['err']
        assert not list(db.scalars(select(Supply)))
