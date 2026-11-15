"""Release 639: full structured supplement facts save/reload and safety tests."""
import json
from html import unescape
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import ChangeAudit, RegimenItem, RegimenProductFacts639, RegimenEntry
from app.routers import regimen635

pytestmark = pytest.mark.quick


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'facts639.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(regimen635.router)
    def isolated():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = isolated
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


FACTS = {
    "brand": "Pure Encapsulations",
    "source": "NIH DSLD",
    "source_id": "218662",
    "serving_quantity": "2",
    "serving_unit": "Capsule(s)",
    "ingredients": [
        {"name": "Vitamin C", "amount": "100", "unit": "mg", "basis": "", "daily_value": ""},
        {"name": "Magnesium", "amount": "25", "unit": "mg", "basis": "", "daily_value": ""},
        {"name": "Zinc", "amount": "0.25", "unit": "mg", "basis": "", "daily_value": ""},
    ],
}


def post(client, path, data):
    response = client.post(
        path, content=urlencode(data),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 303, response.text
    return response


def test_structured_label_persists_and_edit_form_reloads_exact_ingredients(env):
    client, Session = env
    result = post(client, "/regimen/items", {
        "kind": "supplement", "name": "Nutrient 950",
        "label_facts_json": json.dumps(FACTS),
    })
    assert "err=" not in result.headers["location"]
    with Session() as db:
        item = db.scalar(select(RegimenItem))
        facts = db.scalar(select(RegimenProductFacts639))
        assert item.id == facts.item_id
        assert facts.brand == "Pure Encapsulations"
        assert facts.serving_quantity == "2"
        assert facts.serving_unit == "Capsule(s)"
        assert json.loads(facts.ingredients_json) == FACTS["ingredients"]
        assert facts.imported_at is not None
        assert list(db.scalars(select(RegimenEntry))) == []
    page = client.get("/regimen")
    assert page.status_code == 200
    assert "Nutrient 950" in page.text
    decoded = unescape(page.text)
    assert '"serving_quantity": "2"' in decoded
    assert '"source_id": "218662"' in decoded
    assert '"Zinc"' in decoded


def test_edit_updates_label_without_changing_intake_or_item_identity(env):
    client, Session = env
    post(client, "/regimen/items", {
        "kind": "supplement", "name": "Nutrient 950",
        "label_facts_json": json.dumps(FACTS),
    })
    updated = {**FACTS, "serving_quantity": "3", "ingredients": [
        {"name": "Vitamin C", "amount": "120", "unit": "mg", "basis": "", "daily_value": ""},
    ]}
    response = post(client, "/regimen/items/1/edit", {
        "kind": "supplement", "name": "Nutrient 950",
        "active": "yes", "label_facts_json": json.dumps(updated),
    })
    assert "err=" not in response.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1).name == "Nutrient 950"
        facts = db.scalar(select(RegimenProductFacts639))
        assert facts.serving_quantity == "3"
        assert json.loads(facts.ingredients_json) == updated["ingredients"]
        assert len(list(db.scalars(select(RegimenProductFacts639)))) == 1
        assert list(db.scalars(select(RegimenEntry))) == []


def test_invalid_facts_fail_closed_without_creating_item(env):
    client, Session = env
    bad = {**FACTS, "ingredients": [{"name": "Zinc", "amount": "x" * 41, "unit": "mg"}]}
    response = post(client, "/regimen/items", {
        "kind": "supplement", "name": "Invalid Label",
        "label_facts_json": json.dumps(bad),
    })
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert list(db.scalars(select(RegimenItem))) == []
        assert list(db.scalars(select(RegimenProductFacts639))) == []


def test_legacy_manual_item_remains_unchanged(env):
    client, Session = env
    result = post(client, "/regimen/items", {
        "kind": "medication", "name": "Manual Item", "strength": "10 mg",
    })
    assert "err=" not in result.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1).strength == "10 mg"
        assert list(db.scalars(select(RegimenProductFacts639))) == []
