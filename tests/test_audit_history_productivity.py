"""Audit history filtering, pagination, and navigational safety."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import ChangeAudit
from app.routers.reliability import router, _audit_record_url


@pytest.fixture
def audit_client(tmp_path):
    path = tmp_path / "audit-test.sqlite"
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session.begin() as db:
        for index in range(1, 121):
            db.add(ChangeAudit(
                entity_type="vial" if index % 2 else "dose",
                entity_id=7 if index % 3 else 9,
                action="bulk_update" if index % 5 else "reconcile",
                before_json=json.dumps({"old": index}),
                after_json=json.dumps({"new": index}),
            ))

    app = FastAPI()
    app.include_router(router)
    def test_db():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_audit_pagination_clamps_large_pages_and_preserves_filters(audit_client):
    response = audit_client.get("/audit-history?page=999999")
    assert response.status_code == 200
    assert "Page 3 of 3" in response.text
    assert "Showing 101–120" in response.text

    response = audit_client.get(
        "/audit-history?entity_type=vial&entity_id=7&action=bulk_update&page_size=25"
    )
    assert response.status_code == 200
    assert 'name="entity_id"' in response.text
    assert 'value="7"' in response.text
    assert 'name="action"' in response.text
    assert "bulk update" in response.text
    assert 'href="/vials/7"' in response.text


def test_audit_action_select_and_page_size(audit_client):
    response = audit_client.get("/audit-history?page_size=25")
    assert response.status_code == 200
    assert "Page 1 of 5" in response.text
    assert "Showing 1–25" in response.text
    assert 'value="reconcile"' in response.text
    assert "Next" in response.text
    assert "page_size=25" in response.text


def test_audit_invalid_filters_rejected(audit_client):
    for url in (
        "/audit-history?entity_id=-1",
        "/audit-history?entity_id=seven",
        "/audit-history?page_size=999",
    ):
        response = audit_client.get(url)
        assert response.status_code == 400, url


def test_audit_empty_filter_explains_zero_results(audit_client):
    response = audit_client.get("/audit-history?entity_id=999999")
    assert response.status_code == 200
    assert "0 matching event(s)" in response.text
    assert "Showing 0–0" in response.text
    assert "No audit events match these filters." in response.text


def test_audit_record_urls_are_allowlisted():
    assert _audit_record_url("vial", 12) == "/vials/12"
    assert _audit_record_url("dose", 12) == "/doses/12/edit"
    assert _audit_record_url("supply", 12) is None
    assert _audit_record_url("vial", 0) is None
    assert _audit_record_url("unknown", 10) is None
