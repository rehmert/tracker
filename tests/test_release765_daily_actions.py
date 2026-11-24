"""Release 765: read-only exact-record Today attention and Dashboard handoffs.

All data is synthetic and isolated by tests/conftest.py.
"""
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, SessionLocal
from app.main import app
from app.models import Coa, Compound, Protocol, Vial
from app.list_queries297 import vial_listing
from app.daily_summary674 import snapshot674
from app.today_priorities765 import missing_coa_count765, passed_date_examples765

ROOT = Path(__file__).resolve().parents[1]
VIAL_DRILLDOWN = "/vials?status=non_discarded&amp;coa=missing#tracker-vials-sortable"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def add_vial(db, compound, status="sealed", **kwargs):
    vial = Vial(
        compound_id=compound.id, content_value=10, content_unit="mg",
        status=status, unit_price_cents=0, **kwargs,
    )
    db.add(vial)
    db.flush()
    return vial


def test_765_missing_coa_count_exactly_matches_filtered_vials(db):
    compound = Compound(name="Synthetic 765 COA", category="peptide")
    db.add(compound)
    db.flush()
    direct = Coa(original_name="Direct")
    associated = Coa(original_name="Associated")
    db.add_all([direct, associated])
    db.flush()
    add_vial(db, compound, "sealed")
    add_vial(db, compound, "in_use")
    add_vial(db, compound, "finished")
    add_vial(db, compound, "discarded")
    add_vial(db, compound, "sealed", coa=direct)
    v = add_vial(db, compound, "in_use")
    v.linked_coas.append(associated)
    db.flush()
    match = db.scalars(vial_listing("non_discarded", coa="missing")).all()
    assert missing_coa_count765(db) == len(match) == 3
    assert {v.status for v in match} == {"sealed", "in_use", "finished"}
    assert not db.dirty and not db.deleted


def test_765_passed_dates_match_existing_today_scope(db):
    today = date(2026, 11, 23)
    compound = Compound(name="Synthetic 765 dates", category="peptide")
    db.add(compound)
    db.flush()
    recent = add_vial(db, compound, "sealed", expires_on=today - timedelta(days=1))
    older = add_vial(db, compound, "in_use", beyond_use_on=today - timedelta(days=4))
    add_vial(db, compound, "finished", expires_on=today - timedelta(days=1))
    add_vial(db, compound, "discarded", expires_on=today - timedelta(days=1))
    add_vial(db, compound, "sealed", closed_on=today, expires_on=today - timedelta(days=1))
    add_vial(db, compound, "sealed", expires_on=today)
    db.flush()
    examples = passed_date_examples765(db, today)
    assert {v.id for v in examples} == {recent.id, older.id}
    assert snapshot674(db, today)["inventory_attention"] == 2
    assert len(passed_date_examples765(db, today, limit=1)) == 1
    with pytest.raises(ValueError):
        passed_date_examples765(db, today, limit=11)


def test_765_templates_preserve_early_single_recording_bar():
    mobile = (ROOT / "app/templates/mobile_today509.html").read_text()
    dashboard = (ROOT / "app/templates/dashboard.html").read_text()
    css = (ROOT / "app/static/css/tracker-today-priorities765.css").read_text()
    Environment().parse(mobile)
    Environment().parse(dashboard)
    assert mobile.count('class="tracker-daily-actions"') == 1
    assert mobile.count('class="ux674-dashboard"') == 1
    assert mobile.index('class="tracker-daily-actions"') < mobile.index('id="today765-priorities"') < mobile.index('class="ux674-dashboard"')
    assert "tracker-today-priorities765.css?v=765" in mobile
    assert 'href="' + VIAL_DRILLDOWN + '"' in mobile
    assert 'href="/inventory-data-quality?issue=expired"' in mobile
    assert 'href="/vials/{{ vial.id }}"' in mobile
    assert 'href="/protocols/{{ protocol.id }}"' in mobile
    assert 'href="#mobile-schedule-heading"' in mobile
    assert 'href="/mobile#mobile-schedule-heading"' in dashboard
    assert 'href="/mobile#today765-missing-start"' in dashboard
    assert dashboard.count(VIAL_DRILLDOWN) >= 2
    assert "min-height: 44px" in css
    assert "@media (max-width: 389px)" in css
    assert css.count("{") == css.count("}")


def test_765_actual_pages_link_to_exact_records_not_general_managers():
    with TestClient(app, follow_redirects=False) as client:
        with SessionLocal() as db:
            compound = Compound(name="Synthetic 765 mobile actionable", category="peptide")
            db.add(compound)
            db.flush()
            vial = add_vial(
                db, compound, "sealed",
                expires_on=date.today() - timedelta(days=2),
            )
            protocol = Protocol(
                name="Synthetic 765 needs start", is_active=True, start_date=None
            )
            db.add(protocol)
            db.commit()
            vial_id, protocol_id = vial.id, protocol.id
        today = client.get("/mobile")
        overview = client.get("/")
        filtered = client.get("/vials?status=non_discarded&coa=missing")
        target_protocol = client.get(f"/protocols/{protocol_id}")
        assert today.status_code == overview.status_code == filtered.status_code == target_protocol.status_code == 200
        assert 'id="today765-priorities"' in today.text
        assert 'data-today765-kind="coa"' in today.text
        assert 'data-today765-kind="dates"' in today.text
        assert 'data-today765-kind="start"' in today.text
        assert f'href="/vials/{vial_id}"' in today.text
        assert f'href="/protocols/{protocol_id}"' in today.text
        assert "Synthetic 765 mobile actionable" in filtered.text
        assert "Synthetic 765 needs start" in target_protocol.text
        assert 'href="/mobile#today765-missing-start"' in overview.text
        assert VIAL_DRILLDOWN in overview.text
