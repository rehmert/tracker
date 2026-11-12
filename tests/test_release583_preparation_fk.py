"""Release 583: regression for preparation deletion with SQLite FK enforcement.

Exercise the real router handler against an isolated sqlite database,
including edited supply links and exact stock restoration. No live data.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    ChangeAudit, Compound, PreparationEvent, PreparationSupply,
    Purchase, Supply, SupplyUsage, Vial,
)
from app.routers import vials


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'preparation583.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    # Test handler's transaction; the inventory lock itself is exercised
    # in its existing dedicated tests, not bypassed in production.
    monkeypatch.setattr(vials, "reserve_inventory_write", lambda session: True)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def make_preparation(db):
    compound = Compound(name="QA 583 FK compound", category="peptide")
    purchase = Purchase(vendor="QA FK-only", purchased_on=date(2026, 11, 12))
    db.add_all([compound, purchase])
    db.flush()
    vial = Vial(
        compound_id=compound.id, purchase_id=purchase.id,
        content_value=10, content_unit="mg", volume_ml=2,
        status="in_use", form="lyophilized",
    )
    supply = Supply(
        purchase_id=purchase.id, name="QA needles",
        kind="needle", purchased_qty=10, remaining_qty=8,
    )
    db.add_all([vial, supply])
    db.flush()
    preparation = PreparationEvent(
        vial_id=vial.id, kind="filtering", notes="edited 583"
    )
    db.add(preparation)
    db.flush()
    usage = SupplyUsage(supply_id=supply.id, vial_id=vial.id, amount=2)
    db.add(usage)
    db.flush()
    link = PreparationSupply(event_id=preparation.id, usage_id=usage.id)
    db.add(link)
    db.commit()
    return vial.id, preparation.id, supply.id, usage.id, link.id


def test_583_filtering_delete_flushes_fk_links_and_restores_stock(db):
    vial_id, event_id, supply_id, usage_id, link_id = make_preparation(db)
    assert db.scalar(select(Supply.remaining_qty).where(Supply.id == supply_id)) == 8
    response = vials.delete_preparation(vial_id, event_id, db=db)
    assert response.status_code == 303
    db.expire_all()
    assert db.get(PreparationSupply, link_id) is None
    assert db.get(SupplyUsage, usage_id) is None
    assert db.get(PreparationEvent, event_id) is None
    assert db.get(Supply, supply_id).remaining_qty == 10
    audit = db.scalar(select(ChangeAudit).where(
        ChangeAudit.entity_type == "preparation",
        ChangeAudit.entity_id == event_id,
        ChangeAudit.action == "delete",
    ))
    assert audit is not None
    assert '"supplies":' in audit.before_json


def test_583_reconstitution_event_must_not_be_deleted(db):
    vial_id, event_id, supply_id, usage_id, link_id = make_preparation(db)
    event_obj = db.get(PreparationEvent, event_id)
    event_obj.kind = "reconstitution"
    db.commit()
    response = vials.delete_preparation(vial_id, event_id, db=db)
    assert response.status_code == 303
    db.expire_all()
    assert db.get(PreparationEvent, event_id) is not None
    assert db.get(PreparationSupply, link_id) is not None
    assert db.get(SupplyUsage, usage_id) is not None
    assert db.get(Supply, supply_id).remaining_qty == 8
