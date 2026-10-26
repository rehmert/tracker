from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Compound, Vial, DoseLog
from app.routers.inventory_intelligence import inventory_summary


def test_inventory_expiry_and_costs():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Compound(name="Test Compound", category="peptide")
        db.add(c); db.flush()
        v = Vial(compound_id=c.id, label="A", content_value=10, content_unit="mg", status="in_use", unit_price_cents=2000, expires_on=date(2026, 11, 1))
        db.add(v); db.flush()
        db.add(DoseLog(vial_id=v.id, taken_at=__import__("datetime").datetime(2026, 10, 20), entered_value=2, entered_unit="mg", amount_base=2000, kind="dose"))
        db.add(DoseLog(vial_id=v.id, taken_at=__import__("datetime").datetime(2026, 10, 21), entered_value=1, entered_unit="mg", amount_base=1000, kind="waste"))
        db.commit()
        rows, totals = inventory_summary(db, date(2026, 10, 26))
        assert totals["expiring_30"] == 1
        assert totals["expired"] == 0
        assert rows[0]["dose_count"] == 1
        assert rows[0]["used_cost"] == 400
        assert rows[0]["wasted_cost"] == 200
        _, expired = inventory_summary(db, date(2026, 11, 2))
        assert expired["expired"] == 1

def test_inventory_template_and_nav():
    from app.templating import templates
    from pathlib import Path
    assert templates.get_template("inventory_intelligence.html")
    assert "/inventory-intelligence" in (Path(__file__).parents[1] / "app/templates/base.html").read_text()
