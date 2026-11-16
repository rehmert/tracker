"""Release 645: per-upload test types, stable default document and deletion fallback."""
import io
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment, CoaDefaultDocument645


def test_645_edit_test_type_and_select_default_document():
    with TestClient(app) as client:
        with SessionLocal() as db:
            coa = Coa(lab_name="Default view", stored_name="metadata-645")
            db.add(coa)
            db.commit()
            cid = coa.id
        response = client.post(
            f"/coas/{cid}/attachments",
            data={"test_type": "Purity"},
            files=[
                ("files", ("purity.pdf", io.BytesIO(b"%PDF-1.4\npurity645"), "application/pdf")),
                ("files", ("identity.pdf", io.BytesIO(b"%PDF-1.4\nidentity645"), "application/pdf")),
            ],
            follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            first, second = coa.attachments
            first_id, second_id = first.id, second.id

        # Metadata-only COA defaults to first uploaded document.
        response = client.get(f"/coas/{cid}/file")
        assert response.status_code == 200
        assert "purity.pdf" in response.headers["content-disposition"]

        response = client.post(
            f"/coas/{cid}/attachments/{second_id}/test-type",
            data={"test_type": "  Identity  "}, follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            second = db.get(CoaAttachment, second_id)
            assert second.test_type == "Identity"

        response = client.post(
            f"/coas/{cid}/default-file",
            data={"document": str(second_id)}, follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaDefaultDocument645, cid).attachment_id == second_id
        response = client.get(f"/coas/{cid}/file")
        assert "identity.pdf" in response.headers["content-disposition"]

        # Cross-record attachment selection must not change the default.
        with SessionLocal() as db:
            other = Coa(lab_name="Other", stored_name="metadata-other-645")
            db.add(other)
            db.commit()
            oid = other.id
        response = client.post(
            f"/coas/{oid}/default-file",
            data={"document": str(second_id)}, follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaDefaultDocument645, oid) is None
        response = client.post(
            f"/coas/{oid}/attachments/{second_id}/test-type",
            data={"test_type": "Tampered"}, follow_redirects=False,
        )
        assert response.status_code == 404
        with SessionLocal() as db:
            assert db.get(CoaAttachment, second_id).test_type == "Identity"

        response = client.post(
            f"/coas/{cid}/attachments/{second_id}/delete", follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaDefaultDocument645, cid) is None
            assert db.get(CoaAttachment, first_id) is not None
        response = client.get(f"/coas/{cid}/file")
        assert response.status_code == 200
        assert "purity.pdf" in response.headers["content-disposition"]


def test_645_default_original_remains_stable_and_bad_input_does_not_mutate():
    with TestClient(app) as client:
        with SessionLocal() as db:
            coa = Coa(lab_name="Original document", original_name="original.pdf",
                      stored_name="missing-645-file", content_type="application/pdf")
            db.add(coa)
            db.commit()
            cid = coa.id
        assert client.post(f"/coas/{cid}/default-file",
                           data={"document": "999999"}, follow_redirects=False).status_code == 303
        assert client.post(f"/coas/{cid}/default-file",
                           data={"document": "not-a-document"}, follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaDefaultDocument645, cid) is None
        assert client.get(f"/coas/{cid}/file").status_code == 404
        assert client.get(f"/coas/{cid}/original-file").status_code == 404
