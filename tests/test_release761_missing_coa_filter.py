"""Release 761: dashboard no-COA deep link and matching Vials filters.

Isolated synthetic ORM and template contract tests. No live inventory.
"""
from pathlib import Path

import pytest
from jinja2 import Environment
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Coa, Compound, Vial
from app.list_queries297 import vial_listing

ROOT = Path(__file__).resolve().parents[1]


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


def synthetic_vial(db, compound, status, *, coa=None, linked=None):
    v = Vial(
        compound_id=compound.id, content_value=10, content_unit="mg",
        unit_price_cents=0, status=status,
    )
    if coa is not None:
        v.coa = coa
    if linked is not None:
        v.linked_coas.append(linked)
    db.add(v)
    db.flush()
    return v


def test_761_no_coa_matches_dashboard_count_for_active_and_finished(db):
    compound = Compound(name="Synthetic 761 no COA", category="peptide")
    db.add(compound)
    db.flush()
    direct = Coa(original_name="Synthetic legacy COA")
    linked = Coa(original_name="Synthetic linked COA")
    db.add_all([direct, linked])
    db.flush()

    missing_sealed = synthetic_vial(db, compound, "sealed")
    missing_in_use = synthetic_vial(db, compound, "in_use")
    missing_finished = synthetic_vial(db, compound, "finished")
    missing_discarded = synthetic_vial(db, compound, "discarded")
    synthetic_vial(db, compound, "sealed", coa=direct)
    synthetic_vial(db, compound, "in_use", linked=linked)
    db.flush()

    all_vials = db.scalars(vial_listing("all")).all()
    dashboard_ids = {
        v.id for v in all_vials
        if v.status != "discarded" and not v.all_coas
    }
    result = db.scalars(vial_listing("non_discarded", coa="missing")).all()
    assert {v.id for v in result} == dashboard_ids
    assert {v.id for v in result} == {
        missing_sealed.id, missing_in_use.id, missing_finished.id,
    }
    assert missing_discarded.id not in dashboard_ids
    assert len(db.scalars(vial_listing("active", coa="missing")).all()) == 2
    assert {v.id for v in db.scalars(vial_listing("discarded", coa="missing")).all()} == {
        missing_discarded.id,
    }


def test_761_compound_and_coa_filters_combine_without_leaking(db):
    first = Compound(name="Synthetic A", category="peptide")
    second = Compound(name="Synthetic B", category="peptide")
    db.add_all([first, second])
    db.flush()
    match = synthetic_vial(db, first, "finished")
    synthetic_vial(db, second, "sealed")
    linked = Coa(original_name="Other COA")
    db.add(linked)
    db.flush()
    synthetic_vial(db, first, "sealed", linked=linked)
    ids = [v.id for v in db.scalars(
        vial_listing("non_discarded", first.id, "missing")
    ).all()]
    assert ids == [match.id]


def test_761_dashboard_deep_link_matches_vial_filter_controls():
    dashboard = (ROOT / "app/templates/dashboard.html").read_text()
    vials = (ROOT / "app/templates/vials.html").read_text()
    router = (ROOT / "app/routers/vials.py").read_text()
    saved = (ROOT / "app/static/vial_saved_views.js").read_text()
    Environment().parse(dashboard)
    Environment().parse(vials)
    assert 'href="/vials?status=non_discarded&amp;coa=missing#tracker-vials-sortable"' in dashboard
    assert 'name="coa"' in vials
    assert "'non_discarded', 'Not discarded'" in vials
    assert 'Clear COA filter' in vials
    assert "'yes' if v.all_coas else 'none'" in vials
    assert 'coa: str = ""' in router
    assert 'vial_listing(status, compound_id, coa)' in router
    assert 'view.coa === \'missing\'' in saved
    assert 'vial_saved_views.js?v=761' in vials


def test_761_filter_is_read_only_and_base_filters_still_work(db):
    compound = Compound(name="Synthetic read-only", category="peptide")
    db.add(compound)
    db.flush()
    vial = synthetic_vial(db, compound, "sealed")
    db.commit()
    assert [v.id for v in db.scalars(vial_listing("active")).all()] == [vial.id]
    assert [v.id for v in db.scalars(vial_listing("all")).all()] == [vial.id]
    db.scalars(vial_listing("non_discarded", coa="missing")).all()
    assert not db.dirty and not db.new and not db.deleted
