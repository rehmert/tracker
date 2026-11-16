"""Release 643: independent COA test uploads remain under one certificate."""
from io import BytesIO
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import config
from app.db import Base
from app.models import Coa, CoaDocument643
from app.routers import coas
from app.scoped_db390 import get_scoped_db390
from app.attachment_scope396 import require_attachment_scope396
from app.attachment_files400 import require_attachment_workspace400
from app.backup_references341 import required_attachments


@pytest.fixture
def setup(tmp_path, monkeypatch):
    coa_dir = tmp_path / "uploads" / "coa"
    coa_dir.mkdir(parents=True)
    (tmp_path / "uploads" / "labs").mkdir()
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", coa_dir)
    monkeypatch.setattr(coas.services.config, "DATA_DIR", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'tracker.db'}",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Coa(original_name="", stored_name="metadata-a",
                lab_name="Lab 1"),
            Coa(original_name="", stored_name="metadata-b",
                lab_name="Lab 2"),
        ])
        db.commit()
    app = FastAPI()
    app.include_router(coas.router)
    def get_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_scoped_db390] = get_session
    app.dependency_overrides[require_attachment_scope396] = lambda: None
    app.dependency_overrides[require_attachment_workspace400] = lambda: None
    with TestClient(app) as browser:
        yield browser, engine, coa_dir, tmp_path
    engine.dispose()


def fake_pdf(name):
    return ("files", (name, b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
                      "application/pdf"))


def test_643_multiple_files_stay_on_same_coa_and_are_individually_accessible(setup):
    client, engine, directory, data_dir = setup
    response = client.post("/coas/1/edit", data={
        "document_action": "upload", "test_label": "Purity / endotoxin",
    }, files=[fake_pdf("purity.pdf"), fake_pdf("endotoxin.pdf")],
        follow_redirects=False)
    assert response.status_code == 303
    with Session(engine) as db:
        documents = list(db.scalars(select(CoaDocument643).order_by(CoaDocument643.id)))
        assert len(documents) == 2
        assert {document.original_name for document in documents} == {
            "purity.pdf", "endotoxin.pdf",
        }
        assert all(doc.coa_id == 1 for doc in documents)
        assert all(doc.test_label == "Purity / endotoxin" for doc in documents)
        for document in documents:
            assert (directory / document.stored_name).is_file()
            result = client.get(f"/coas/1/file?document_id={document.id}")
            assert result.status_code == 200
            assert result.content.startswith(b"%PDF-1.4")
            assert client.get(f"/coas/2/file?document_id={document.id}").status_code == 404
    assert len(required_attachments(data_dir / "tracker.db")) == 2


def test_643_remove_one_document_does_not_remove_others(setup):
    client, engine, directory, _ = setup
    assert client.post("/coas/1/edit", data={"document_action": "upload"},
                       files=[fake_pdf("one.pdf"), fake_pdf("two.pdf")],
                       follow_redirects=False).status_code == 303
    with Session(engine) as db:
        documents = list(db.scalars(select(CoaDocument643).order_by(CoaDocument643.id)))
        first, second = documents
        first_file, second_file = first.stored_name, second.stored_name
        first_id = first.id
    denied = client.post("/coas/2/edit", data={
        "document_action": "remove", "document_id": str(first_id),
    }, follow_redirects=False)
    assert denied.status_code == 404
    assert client.post("/coas/1/edit", data={
        "document_action": "remove", "document_id": str(first_id),
    }, follow_redirects=False).status_code == 303
    assert not (directory / first_file).exists()
    assert (directory / second_file).is_file()
    with Session(engine) as db:
        remaining = list(db.scalars(select(CoaDocument643)))
        assert len(remaining) == 1 and remaining[0].stored_name == second_file


def test_643_invalid_member_aborts_batch_and_preserves_original(setup):
    client, engine, directory, _ = setup
    original = directory / "primary.pdf"
    original.write_bytes(b"%PDF-1.4\nprimary")
    with Session(engine) as db:
        db.get(Coa, 1).original_name = "primary.pdf"
        db.get(Coa, 1).stored_name = "primary.pdf"
        db.commit()
    response = client.post("/coas/1/edit", data={"document_action": "upload"},
        files=[fake_pdf("valid.pdf"),
               ("files", ("invalid.txt", b"bad", "text/plain"))],
        follow_redirects=False)
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    with Session(engine) as db:
        assert list(db.scalars(select(CoaDocument643))) == []
        assert db.get(Coa, 1).original_name == "primary.pdf"
    assert list(directory.iterdir()) == [original]


def test_643_deleting_coa_removes_all_its_documents(setup):
    client, engine, directory, _ = setup
    assert client.post("/coas/1/edit", data={"document_action": "upload"},
                       files=[fake_pdf("purity.pdf"), fake_pdf("identity.pdf")],
                       follow_redirects=False).status_code == 303
    assert client.post("/coas/1/delete", follow_redirects=False).status_code == 303
    with Session(engine) as db:
        assert db.get(Coa, 1) is None
        assert list(db.scalars(select(CoaDocument643))) == []
        assert db.get(Coa, 2) is not None
    assert not list(directory.iterdir())
