"""Release 774: atomic Google Tasks bulk title save, visible-source safety, and UX.

All records are synthetic, in-memory; no OAuth, Google, or live Tracker data.
"""
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.google_tasks_models769 import GoogleTasksTitle773
from app.google_tasks_projection769 import projected769
from app.models import Compound, Protocol, ProtocolItem, RegimenItem, RegimenSchedule
from app.routers import google_tasks769 as google

BATCH = "/integrations/google-tasks/titles"
TEMPLATE = Path(__file__).resolve().parents[1] / "app/templates/google_tasks769.html"


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Factory() as db:
        med = RegimenItem(kind="medication", name="Synthetic Long Medicine", active=True)
        supp = RegimenItem(kind="supplement", name="Synthetic Detailed Vitamin", active=True)
        db.add_all([med, supp])
        db.flush()
        db.add_all([
            RegimenSchedule(item_id=med.id, cadence="daily", amount="1 tablet",
                            start_on=date(2026,11,24), at_time="07:30", active=True),
            RegimenSchedule(item_id=supp.id, cadence="daily", amount="1 capsule",
                            start_on=date(2026,11,24), at_time="21:00", active=True),
        ])
        compound = Compound(name="Synthetic Full Compound", category="peptide")
        db.add(compound)
        db.flush()
        active = Protocol(name="Active synthetic protocol", is_active=True,
                          start_date=date(2026,11,24))
        inactive = Protocol(name="What-if synthetic protocol", is_active=False,
                            start_date=date(2026,11,24))
        db.add_all([active, inactive])
        db.flush()
        db.add_all([
            ProtocolItem(protocol_id=active.id, compound_id=compound.id,
                         position=0, amount_value=1.5, amount_unit="mg",
                         freq_count=1, freq_period="interval", start_week=1,
                         dose_time="20:00"),
            ProtocolItem(protocol_id=inactive.id, compound_id=compound.id,
                         position=0, amount_value=3, amount_unit="mg",
                         freq_count=1, freq_period="interval", start_week=1,
                         dose_time="20:00"),
        ])
        db.add(GoogleTasksTitle773(kind="protocol", source_id=2, title="Preserve hidden"))
        db.commit()
    monkeypatch.setattr(google, "render", lambda request, name, **context: context)
    monkeypatch.setattr(google.config, "instance_label", lambda: "DEV")
    app = FastAPI()
    app.include_router(google.router)
    def dependency():
        with Factory() as db:
            yield db
    app.dependency_overrides[google.get_scoped_db390] = dependency
    with TestClient(app, follow_redirects=False) as client:
        yield Factory, client
    engine.dispose()


def fields(*, med="Med", supp="Vitamin", protocol="HGH"):
    return {
        "title_medication_1": med,
        "title_supplement_2": supp,
        "title_protocol_1": protocol,
    }


def overrides(Factory):
    with Factory() as db:
        return {
            (row.kind, row.source_id): row.title
            for row in db.scalars(select(GoogleTasksTitle773))
        }


def test_774_single_post_saves_all_three_categories_and_preserves_origins(env):
    Factory, client = env
    response = client.post(BATCH, data=fields(med="  Medicine  ",
                                             supp="Vitamin   D", protocol="HGH"))
    assert response.status_code == 303
    assert "Saved%203" in response.headers["location"]
    assert overrides(Factory) == {
        ("medication", 1): "Medicine",
        ("supplement", 2): "Vitamin D",
        ("protocol", 1): "HGH",
        ("protocol", 2): "Preserve hidden",
    }
    with Factory() as db:
        projected = projected769(db, date(2026,11,24), 1)
        titles = {occ.kind: occ.title for occ in projected.values()}
        assert titles == {
            "medication": "07:30 · Medicine",
            "supplement": "21:00 · Vitamin D",
            "protocol": "20:00 · HGH",
        }
        assert db.get(RegimenItem, 1).name == "Synthetic Long Medicine"
        assert db.get(Protocol, 1).name == "Active synthetic protocol"
        assert all("Tracker ID: t769:" in occ.task_body()["notes"]
                   for occ in projected.values())


def test_774_change_one_clear_another_leave_third_and_idempotent_save(env):
    Factory, client = env
    client.post(BATCH, data=fields())
    response = client.post(BATCH, data=fields(med="Med 2", supp="", protocol="HGH"))
    assert response.status_code == 303
    assert overrides(Factory) == {
        ("medication", 1): "Med 2", ("protocol", 1): "HGH",
        ("protocol", 2): "Preserve hidden",
    }
    unchanged = client.post(BATCH, data=fields(med="Med 2", supp="", protocol="HGH"))
    assert "Saved%200" in unchanged.headers["location"]
    with Factory() as db:
        titles = [x.title for x in projected769(db, date(2026,11,24), 1).values()]
        assert "21:00 · Synthetic Detailed Vitamin — 1 capsule" in titles


@pytest.mark.parametrize("data,status", [
    (fields(med="A" * 81), 400),
    (fields(supp="two\nlines"), 400),
    (fields(protocol="bad\x7fvalue"), 400),
    ({"title_medication_1": "Med", "title_protocol_1": "HGH"}, 409),
    ({**fields(), "title_protocol_2": "Should not edit what-if"}, 409),
    ({**fields(), "title_medication_900": "Unknown"}, 409),
    ({**fields(), "malformed": "Value"}, 400),
])
def test_774_rejects_invalid_or_stale_submission_atomically(env, data, status):
    Factory, client = env
    before = overrides(Factory)
    response = client.post(BATCH, data=data)
    assert response.status_code == status
    assert overrides(Factory) == before


def test_774_duplicate_title_field_rejected_without_partial_write(env):
    Factory, client = env
    body = (
        "title_medication_1=First&title_medication_1=Second&"
        "title_supplement_2=Vitamin&title_protocol_1=HGH"
    )
    response = client.post(
        BATCH, content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert overrides(Factory) == {("protocol", 2): "Preserve hidden"}


def test_774_deactivated_protocol_between_load_and_save_refuses_stale_form(env):
    Factory, client = env
    with Factory() as db:
        db.get(Protocol, 1).is_active = False
        db.commit()
    response = client.post(BATCH, data=fields())
    assert response.status_code == 409
    assert overrides(Factory) == {("protocol", 2): "Preserve hidden"}


def test_774_ui_has_shared_form_controls_and_separate_include_forms(env):
    Factory, _ = env
    markup = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="google-task-titles-form"' in markup
    assert 'action="/integrations/google-tasks/titles"' in markup
    assert 'name="title_{{ s.kind }}_{{ s.id }}"' in markup
    assert 'form="google-task-titles-form"' in markup
    assert markup.count('form="google-task-titles-form">Save all titles') == 2
    assert 'action="/integrations/google-tasks/title/{{ s.kind }}/{{ s.id }}"' not in markup
    assert 'action="/integrations/google-tasks/source/{{ s.kind }}/{{ s.id }}"' in markup
    with Factory() as db:
        context = google.settings769(None, db)
        assert len(context["sources"]) == 3
        assert len([s for s in context["sources"] if s["kind"] == "protocol"]) == 1


def test_777_browser_injected_csrf_token_preserves_atomic_batch_save(env):
    """Every real Tracker POST form includes this framework-injected field."""
    Factory, client = env
    data = {**fields(med=" Med Short ", supp="Vitamin D", protocol="HGH"),
            "csrf_token": "synthetic-signature-not-a-real-token"}
    response = client.post(BATCH, data=data)
    assert response.status_code == 303
    assert "Saved%203" in response.headers["location"]
    assert overrides(Factory) == {
        ("medication", 1): "Med Short",
        ("supplement", 2): "Vitamin D",
        ("protocol", 1): "HGH",
        ("protocol", 2): "Preserve hidden",
    }
    with Factory() as db:
        titles = {row.kind: row.title for row in
                  projected769(db, date(2026,11,24), 1).values()}
        assert titles["medication"] == "07:30 · Med Short"
        assert titles["supplement"] == "21:00 · Vitamin D"
        assert titles["protocol"] == "20:00 · HGH"


def test_777_duplicate_csrf_field_rejected_before_any_write(env):
    Factory, client = env
    body = ("title_medication_1=Med&title_supplement_2=Vitamin&"
            "title_protocol_1=HGH&csrf_token=one&csrf_token=two")
    response = client.post(
        BATCH, content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert overrides(Factory) == {("protocol", 2): "Preserve hidden"}


def test_777_csrf_does_not_permit_unexpected_fields_or_bad_title(env):
    Factory, client = env
    response = client.post(BATCH, data={
        **fields(), "csrf_token": "synthetic-token", "unrecognized": "value",
    })
    assert response.status_code == 400
    assert overrides(Factory) == {("protocol", 2): "Preserve hidden"}
    response = client.post(BATCH, data={
        **fields(med="bad" + chr(10) + "value"), "csrf_token": "synthetic-token",
    })
    assert response.status_code == 400
    assert overrides(Factory) == {("protocol", 2): "Preserve hidden"}


def test_777_uses_existing_csrf_field_contract():
    from app.csrf_runtime import FIELD_NAME
    script = (
        Path(__file__).resolve().parents[1] /
        "app/static/js/tracker-csrf-browser.js"
    ).read_text(encoding="utf-8")
    assert FIELD_NAME == "csrf_token"
    assert "const FIELD = 'csrf_token';" in script
    assert "form.appendChild(field)" in script
