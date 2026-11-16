"""Release 650: first and subsequent COA files share edit/default/remove behavior.

All tests run against isolated TRACKER_DATA_DIR. Never against live PROD files.
"""
from uuid import uuid4
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from app.main import app
from app.db import SessionLocal, engine
from app.models import Coa, CoaAttachment, CoaDefaultDocument645, CoaRevision, Compound, Vial
from app.attachment_files400 import attachment_directory400


@pytest.fixture(scope="module", autouse=True)
def _start_isolated_tracker_schema650():
    """Match existing COA suites: run FastAPI lifespan before DB fixture inserts.

    Each pytest worker's conftest has already selected an isolated data
    directory. The lifespan runs migrations and creates all model tables.
    TestClient without a context manager does not enter the lifespan.
    """
    with TestClient(app):
        pass
    # Fast feedback when this module runs independently in a fresh pytest
    # worker; schema checks occur before any COA test tries INSERT.
    tables = inspect(engine)
    assert all(tables.has_table(name) for name in (
        "coas", "coa_attachments", "compounds", "vials"
    )), "Tracker test lifespan did not initialize the isolated database"


def _fixture(*, original=True, extra=True):
    token = uuid4().hex
    original_stored = f"qa650-first-{token}.pdf"
    extra_stored = f"qa650-second-{token}.pdf"
    with SessionLocal() as db:
        coa = Coa(
            lab_name=f"QA650 {token}",
            original_name="first-report.pdf" if original else "",
            stored_name=original_stored if original else f"metadata-{token}",
            content_type="application/pdf" if original else "",
            size_bytes=25 if original else 0,
            sha256="a" * 64 if original else "",
        )
        db.add(coa)
        db.flush()
        cid = coa.id
        eid = None
        if extra:
            attachment = CoaAttachment(
                coa_id=cid, test_type="Sterility", original_name="second-report.pdf",
                stored_name=extra_stored, content_type="application/pdf",
                size_bytes=22, sha256="b" * 64,
            )
            db.add(attachment)
            db.flush()
            eid = attachment.id
        db.commit()
    directory = attachment_directory400("coa")
    if original:
        (directory / original_stored).write_bytes(b"%PDF-1.4\nqa650 first\n")
    if extra:
        (directory / extra_stored).write_bytes(b"%PDF-1.4\nqa650 second\n")
    return cid, eid, original_stored, extra_stored


def _clean(*files):
    directory = attachment_directory400("coa")
    for filename in files:
        (directory / filename).unlink(missing_ok=True)


def _form(*, first_before="", first_after="Purity & identity",
          second_id=None, second_before="Sterility", second_after="Sterility"):
    fields = {
        "original_test_type_original": first_before,
        "test_type_original": first_after,
        "custom_test_type_original": "",
    }
    if second_id is not None:
        fields.update({
            f"original_test_type_{second_id}": second_before,
            f"test_type_{second_id}": second_after,
            f"custom_test_type_{second_id}": "",
        })
    return fields


def test_650_legacy_first_document_can_be_typed_with_ordinary_batch_save():
    cid, second_id, first, second = _fixture()
    try:
        with TestClient(app) as client:
            with SessionLocal() as db:
                assert not list(db.scalars(select(CoaAttachment).where(
                    CoaAttachment.stored_name == first)))
            before = client.get(f"/coas/{cid}")
            assert before.status_code == 200
            assert before.text.count(f'href="/coas/{cid}/original-file"') == 1
            assert 'name="test_type_original"' in before.text
            assert 'name="document" value="original"' in before.text
            assert "Purity + identity" in before.text
            # Viewing must not create a mirror or any audit revision.
            with SessionLocal() as db:
                assert not list(db.scalars(select(CoaAttachment).where(
                    CoaAttachment.stored_name == first)))

            saved = client.post(
                f"/coas/{cid}/attachments/test-types",
                data=_form(second_id=second_id, second_after="Endotoxin"),
                headers={"Accept": "application/json"},
            )
            assert saved.status_code == 200, saved.text
            assert saved.json()["types"] == {
                "original": "Purity & identity",
                str(second_id): "Endotoxin",
            }
            assert saved.json()["updated"] == 2
            with SessionLocal() as db:
                mirror = db.scalar(select(CoaAttachment).where(
                    CoaAttachment.stored_name == first))
                assert mirror is not None and mirror.coa_id == cid
                assert mirror.test_type == "Purity & identity"
                assert mirror.original_name == "first-report.pdf"
                assert db.get(CoaAttachment, second_id).test_type == "Endotoxin"
                assert len(list(db.scalars(select(CoaRevision).where(
                    CoaRevision.coa_id == cid,
                    CoaRevision.event == "attachment_test_types_bulk",
                )))) == 1
            after = client.get(f"/coas/{cid}").text
            assert after.count(f'href="/coas/{cid}/original-file"') == 1
            assert 'name="original_test_type_original" value="Purity &amp; identity"' in after
            assert "Save default document" in after
            assert client.get(f"/coas/{cid}/file").headers["content-disposition"].find("first-report.pdf") >= 0
    finally:
        _clean(first, second)


def test_650_default_radio_targets_any_file_and_rejects_foreign_file():
    cid, second_id, first, second = _fixture()
    other, other_id, other_first, other_second = _fixture()
    try:
        with TestClient(app) as client:
            html = client.get(f"/coas/{cid}").text
            assert html.count('name="document" value=') == 2
            assert html.count('aria-label="Make ') == 2
            response = client.post(
                f"/coas/{cid}/default-file", data={"document": str(second_id)},
                follow_redirects=False,
            )
            assert response.status_code == 303
            assert "second-report.pdf" in client.get(f"/coas/{cid}/file").headers["content-disposition"]
            with SessionLocal() as db:
                assert db.get(CoaDefaultDocument645, cid).attachment_id == second_id
            assert client.post(
                f"/coas/{cid}/default-file", data={"document": str(other_id)},
                follow_redirects=False,
            ).status_code == 303
            with SessionLocal() as db:
                assert db.get(CoaDefaultDocument645, cid).attachment_id == second_id
            assert client.post(
                f"/coas/{cid}/default-file", data={"document": "original"},
                follow_redirects=False,
            ).status_code == 303
            assert "first-report.pdf" in client.get(f"/coas/{cid}/file").headers["content-disposition"]
            with SessionLocal() as db:
                assert db.get(CoaDefaultDocument645, cid) is None
    finally:
        _clean(first, second, other_first, other_second)


def test_650_removing_untouched_first_document_does_not_remove_other_files():
    cid, second_id, first, second = _fixture()
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/coas/{cid}/attachments/0/delete", follow_redirects=False)
            assert response.status_code == 303
            assert client.get(f"/coas/{cid}/original-file").status_code == 404
            assert client.get(f"/coas/{cid}/attachments/{second_id}/file").status_code == 200
            assert "second-report.pdf" in client.get(f"/coas/{cid}/file").headers["content-disposition"]
            with SessionLocal() as db:
                record = db.get(Coa, cid)
                assert record.original_name == ""
                assert len(record.attachments) == 1
            assert not (attachment_directory400("coa") / first).exists()
    finally:
        _clean(first, second)


def test_650_removing_typed_first_document_clears_compatibility_alias():
    cid, second_id, first, second = _fixture()
    try:
        with TestClient(app) as client:
            saved = client.post(
                f"/coas/{cid}/attachments/test-types",
                data=_form(second_id=second_id),
                headers={"Accept": "application/json"},
            )
            assert saved.status_code == 200
            with SessionLocal() as db:
                mirror = db.scalar(select(CoaAttachment).where(
                    CoaAttachment.stored_name == first))
                mid = mirror.id
            assert client.post(f"/coas/{cid}/attachments/{mid}/delete",
                               follow_redirects=False).status_code == 303
            with SessionLocal() as db:
                assert db.get(CoaAttachment, mid) is None
                assert db.get(Coa, cid).original_name == ""
                assert db.get(CoaAttachment, second_id) is not None
            assert client.get(f"/coas/{cid}/original-file").status_code == 404
            assert not (attachment_directory400("coa") / first).exists()
    finally:
        _clean(first, second)


def test_650_legacy_file_replacement_updates_existing_attachment_not_duplicate():
    cid, second_id, first, second = _fixture()
    # Direct legacy update API kept for external clients; UI uses add-documents.
    try:
        with TestClient(app) as client:
            client.post(
                f"/coas/{cid}/attachments/test-types",
                data=_form(second_id=second_id),
                headers={"Accept": "application/json"},
            )
            with SessionLocal() as db:
                mirror = db.scalar(select(CoaAttachment).where(
                    CoaAttachment.stored_name == first))
                mid = mirror.id
            import io
            response = client.post(
                f"/coas/{cid}/edit",
                files={"file": ("replacement.pdf", io.BytesIO(b"%PDF-1.4\nreplacement"), "application/pdf")},
                data={"endotoxin_result_kind": "lt1"},
                follow_redirects=False,
            )
            assert response.status_code == 303
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                mirror = db.get(CoaAttachment, mid)
                assert mirror is not None
                assert coa.original_name == "replacement.pdf"
                assert mirror.original_name == "replacement.pdf"
                assert mirror.stored_name == coa.stored_name
                assert mirror.test_type == "Purity & identity"
                replacement_file = mirror.stored_name
            assert client.get(f"/coas/{cid}/file").status_code == 200
            assert not (attachment_directory400("coa") / first).exists()
            assert client.get(f"/coas/{cid}").text.count("replacement.pdf") >= 1
    finally:
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            if coa and coa.original_name:
                _clean(coa.stored_name)
        _clean(first, second)


def test_650_new_initial_upload_creates_editable_document_on_first_write():
    # Direct COA creation via a vial must no longer strand its first PDF outside
    # the regular attachment model. Keep the legacy fields for old external URLs.
    import io
    token = uuid4().hex
    with SessionLocal() as db:
        compound = Compound(name=f"QA650-compound-{token}", category="peptide")
        db.add(compound)
        db.flush()
        vial = Vial(compound_id=compound.id, content_value=10.0,
                    content_unit="mg", label=f"QA650-{token}")
        db.add(vial)
        db.commit()
        vid = vial.id
    stored = None
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/vials/{vid}/coas",
                files={"file": ("first-new.pdf", io.BytesIO(
                    b"%PDF-1.4\nnew first COA 650\n"), "application/pdf")},
                data={"job_id": token, "endotoxin_result_kind": "lt1"},
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            with SessionLocal() as db:
                record = db.scalar(select(Coa).where(Coa.job_id == token))
                assert record is not None
                cid = record.id
                stored = record.stored_name
                mirror = [x for x in record.attachments if x.stored_name == stored]
                assert len(mirror) == 1
                assert mirror[0].original_name == "first-new.pdf"
                assert mirror[0].test_type == ""
                assert record.original_name == "first-new.pdf"
            html = client.get(f"/coas/{cid}").text
            assert html.count(f'href="/coas/{cid}/original-file"') == 1
            assert html.count("first-new.pdf") >= 1
            assert 'name="test_type_original"' in html
            assert 'name="document" value="original"' in html
            assert "Save all test types" in html
            assert client.get(f"/coas/{cid}/file").status_code == 200
    finally:
        if stored:
            _clean(stored)
