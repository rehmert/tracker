"""Release 647: edit all COA attachment types with one atomic, no-reload save."""
from uuid import uuid4
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment, CoaRevision


def _fixture():
    token = uuid4().hex
    with SessionLocal() as db:
        coa = Coa(lab_name="Bulk 647", stored_name=f"metadata-{token}")
        db.add(coa)
        db.flush()
        for name, label in (("purity.pdf", "Purity"), ("identity.pdf", "Identity")):
            db.add(CoaAttachment(
                coa_id=coa.id, test_type=label, original_name=name,
                stored_name=f"{uuid4().hex}.pdf", content_type="application/pdf",
                size_bytes=12, sha256="a" * 64,
            ))
        db.commit()
        return coa.id, [a.id for a in coa.attachments]


def _fields(ids, types=("Purity", "Identity"), selected=None, customs=None):
    selected = selected or types
    customs = customs or ("", "")
    values = {}
    for aid, before, choice, custom in zip(ids, types, selected, customs):
        values[f"original_test_type_{aid}"] = before
        values[f"test_type_{aid}"] = choice
        values[f"custom_test_type_{aid}"] = custom
    return values


def _snapshot(cid):
    with SessionLocal() as db:
        coa = db.get(Coa, cid)
        values = {item.id: item.test_type for item in coa.attachments}
        revisions = list(db.scalars(select(CoaRevision).where(
            CoaRevision.coa_id == cid,
            CoaRevision.event == "attachment_test_types_bulk",
        )))
        return values, len(revisions)


def test_647_single_form_for_all_documents_without_per_row_save():
    with TestClient(app) as client:
        cid, ids = _fixture()
        html = client.get(f"/coas/{cid}").text
        assert 'id="coa-bulk-test-types"' in html
        assert "Save all test types" in html
        assert 'data-coa-bulk-form' in html
        assert 'data-coa-bulk-save' in html
        assert "tracker-coa-types647.js?v=647" in html
        assert 'data-coa-bulk-status' in html
        assert 'class="coa-test-save"' not in html
        for aid in ids:
            assert f'name="test_type_{aid}" form="coa-bulk-test-types"' in html
            assert f'name="original_test_type_{aid}" value="' in html
            assert f'name="custom_test_type_{aid}"' in html
        assert "data-coa-default-option" in html


def test_647_two_updates_one_commit_one_revision():
    with TestClient(app) as client:
        cid, ids = _fixture()
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=_fields(ids, selected=("Endotoxin", "__custom__"),
                         customs=("", "Hormone assay LC-MS")),
            headers={"Accept": "application/json"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["updated"] == 2
        assert payload["types"] == {str(ids[0]): "Endotoxin", str(ids[1]): "Hormone assay LC-MS"}
        assert _snapshot(cid) == ({ids[0]: "Endotoxin", ids[1]: "Hormone assay LC-MS"}, 1)
        again = client.post(f"/coas/{cid}/attachments/test-types",
            data=_fields(ids, types=("Endotoxin", "Hormone assay LC-MS"),
                         selected=("Endotoxin", "Hormone assay LC-MS")),
            headers={"Accept": "application/json"})
        assert again.status_code == 200
        assert again.json()["updated"] == 0
        assert _snapshot(cid)[1] == 1


def test_647_invalid_row_rejects_entire_batch_without_revision():
    with TestClient(app) as client:
        cid, ids = _fixture()
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=_fields(ids, selected=("Endotoxin", "__custom__")),
            headers={"Accept": "application/json"})
        assert response.status_code == 400
        assert response.json()["ok"] is False
        assert _snapshot(cid) == ({ids[0]: "Purity", ids[1]: "Identity"}, 0)
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=_fields(ids, selected=("Endotoxin", "__custom__"),
                         customs=("", "x" * 121)),
            headers={"Accept": "application/json"})
        assert response.status_code == 400
        assert _snapshot(cid)[1] == 0


def test_647_stale_or_cross_coa_fields_reject_entire_batch():
    with TestClient(app) as client:
        cid, ids = _fixture()
        other, other_ids = _fixture()
        data = _fields(ids, selected=("Endotoxin", "Sterility"))
        data[f"test_type_{other_ids[0]}"] = "TFA"
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=data, headers={"Accept": "application/json"})
        assert response.status_code == 409
        assert _snapshot(cid)[1] == 0
        assert _snapshot(other)[1] == 0
        data = _fields(ids, selected=("Endotoxin", "Sterility"))
        data[f"original_test_type_{ids[1]}"] = "outdated"
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=data, headers={"Accept": "application/json"})
        assert response.status_code == 409
        assert _snapshot(cid) == ({ids[0]: "Purity", ids[1]: "Identity"}, 0)
        # Even a valid proposed first row cannot be partially committed.
        assert "Document list changed" in client.post(
            f"/coas/{cid}/attachments/test-types",
            data={f"test_type_{ids[0]}": "Endotoxin"},
            headers={"Accept": "application/json"}).json()["error"]


def test_647_plain_html_form_fallback_returns_document_anchor():
    with TestClient(app) as client:
        cid, ids = _fixture()
        response = client.post(f"/coas/{cid}/attachments/test-types",
            data=_fields(ids, selected=("TFA", "BA/BB")), follow_redirects=False)
        assert response.status_code == 303
        assert "#test-documents" in response.headers["location"]
        assert _snapshot(cid) == ({ids[0]: "TFA", ids[1]: "BA/BB"}, 1)


def test_647_save_does_not_trigger_browser_navigation_contract():
    source = (Path(__file__).resolve().parents[1] /
              "app/static/js/tracker-coa-types647.js").read_text()
    assert 'form.addEventListener("submit", async event =>' in source
    assert "event.preventDefault()" in source
    assert "new FormData(form)" in source
    assert "fetch(form.action" in source
    assert 'credentials: "same-origin"' in source
    assert "window.location" not in source
    assert "location.reload" not in source
