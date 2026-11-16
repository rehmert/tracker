"""Multiple test documents on one COA: additive upload, isolated deletion and backups."""
import io
import sqlite3

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment
from app.backup_references341 import required_attachments


def test_multiple_coa_documents_keep_original_and_independent_files():
    with TestClient(app) as client:
        with SessionLocal() as db:
            coa = Coa(lab_name="Multiple tests", stored_name="metadata-multiple-test")
            db.add(coa)
            db.commit()
            cid = coa.id

        result = client.post(
            f"/coas/{cid}/attachments",
            data={"test_type": "Purity"},
            files=[
                ("files", ("purity.pdf", io.BytesIO(b"%PDF-1.4\\npurity"), "application/pdf")),
                ("files", ("identity.pdf", io.BytesIO(b"%PDF-1.4\\nidentity"), "application/pdf")),
            ],
            follow_redirects=False,
        )
        assert result.status_code == 303
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            assert coa.original_name == ""
            assert len(coa.attachments) == 2
            first, second = coa.attachments
            assert first.test_type == second.test_type == "Purity"
            first_id, second_id = first.id, second.id
            first_stored, second_stored = first.stored_name, second.stored_name

        assert client.get(f"/coas/{cid}").status_code == 200
        assert client.get(f"/coas/{cid}/attachments/{first_id}/file").status_code == 200
        assert client.get(f"/coas/{cid}/attachments/{second_id}/file").status_code == 200
        assert client.get(f"/coas/{cid}/attachments/999999/file").status_code == 404

        result = client.post(f"/coas/{cid}/attachments/{first_id}/delete", follow_redirects=False)
        assert result.status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, first_id) is None
            assert db.get(CoaAttachment, second_id) is not None
            assert db.get(Coa, cid) is not None
        assert client.get(f"/coas/{cid}/attachments/{second_id}/file").status_code == 200

        client.post(f"/coas/{cid}/delete", follow_redirects=False)
        with SessionLocal() as db:
            assert db.get(CoaAttachment, second_id) is None


def test_backup_requires_additional_coa_documents(tmp_path):
    database = tmp_path / "backup.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE coa_attachments (stored_name TEXT, original_name TEXT)")
        db.execute("INSERT INTO coa_attachments VALUES (?, ?)", ("test-report.pdf", "purity.pdf"))
    assert "uploads/coa/test-report.pdf" in required_attachments(database)
