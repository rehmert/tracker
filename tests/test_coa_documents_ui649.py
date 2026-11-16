"""Release 649: one COA document list and collapsed, retained audit details.

These tests run only against the isolated TRACKER_DATA_DIR configured by QA;
the original legacy file and additional attachment records remain separate.
"""
from uuid import uuid4
from html.parser import HTMLParser

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.attachment_files400 import attachment_directory400
from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment, CoaRevision, CoaDefaultDocument645


class _CoaMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.details = []
        self.tr = 0
        self.labels = []
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a":
            self.links.append(attributes.get("href", ""))
        if tag == "details":
            self.details.append(attributes)
        if tag == "tr":
            self.tr += 1


def _create(*, original=True, reports=("purity.pdf", "identity.pdf"), revisions=2):
    token = uuid4().hex
    stored_names = []
    with SessionLocal() as db:
        stored_original = f"{token}-original.pdf" if original else f"metadata-{token}"
        record = Coa(
            lab_name=f"QA649 {token}",
            original_name="original-report.pdf" if original else "",
            stored_name=stored_original,
            content_type="application/pdf" if original else "",
            size_bytes=18 if original else 0,
        )
        db.add(record)
        db.flush()
        for name in reports:
            stored = f"{uuid4().hex}.pdf"
            stored_names.append(stored)
            db.add(CoaAttachment(
                coa_id=record.id, test_type="Purity",
                original_name=name, stored_name=stored,
                content_type="application/pdf", size_bytes=16,
                sha256="a" * 64,
            ))
        for index in range(revisions):
            db.add(CoaRevision(
                coa_id=record.id, event=f"qa649_event_{index}",
                snapshot_json='{"record": "original metadata", "revision": %d}' % index,
            ))
        db.commit()
        cid = record.id
        aid_list = [item.id for item in record.attachments]
    if original:
        stored_names.insert(0, stored_original)
    directory = attachment_directory400("coa")
    for stored in stored_names:
        (directory / stored).write_bytes(b"%PDF-1.4\nQA649 test file\n")
    return cid, aid_list, stored_names


def _cleanup(stored_names):
    directory = attachment_directory400("coa")
    for stored in stored_names:
        (directory / stored).unlink(missing_ok=True)


def test_649_original_is_one_row_and_one_review_link_among_uploaded_documents():
    with TestClient(app) as client:
        cid, aids, stored = _create()
        try:
            html = client.get(f"/coas/{cid}").text
            markup = _CoaMarkup()
            markup.feed(html)
            assert "<h2>Uploaded documents</h2>" in html
            assert 'data-coa-original-document' in html
            original = f"/coas/{cid}/original-file"
            assert markup.links.count(original) == 1
            assert html.index(original) < html.index(f"/coas/{cid}/attachments/{aids[0]}/file")
            for aid in aids:
                url = f"/coas/{cid}/attachments/{aid}/file"
                assert markup.links.count(url) == 1
                response = client.get(url)
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("application/pdf")
            response = client.get(original)
            assert response.status_code == 200
            assert 'original-report.pdf' in response.headers["content-disposition"]
            assert '<span class="coa-document-origin">Original</span>' in html
            assert "Save all test types" in html
            assert 'name="test_type_%s"' % aids[0] in html
            assert "/default-file" not in html
            assert 'View default COA document' not in html
            assert 'View existing document:' not in html
            assert 'data-coa-default-option' not in html
            # Legacy stable default-file endpoint remains functional for
            # links elsewhere in Tracker, but isn't duplicated in this editor.
            assert client.get(f"/coas/{cid}/file").status_code == 200
        finally:
            _cleanup(stored)


def test_649_original_only_and_metadata_only_render_unified_table_safely():
    with TestClient(app) as client:
        cid, aids, stored = _create(reports=(), revisions=0)
        try:
            html = client.get(f"/coas/{cid}").text
            assert html.count(f'href="/coas/{cid}/original-file"') == 1
            assert "No documents uploaded yet." not in html
            assert "Save all test types" not in html
        finally:
            _cleanup(stored)
        empty, _, empty_files = _create(original=False, reports=(), revisions=0)
        try:
            html = client.get(f"/coas/{empty}").text
            assert "No documents uploaded yet." in html
            assert "/original-file" not in html
            assert "Save all test types" not in html
        finally:
            _cleanup(empty_files)


def test_649_audit_history_is_collapsed_but_each_revision_stays_available():
    with TestClient(app) as client:
        cid, aids, stored = _create()
        try:
            with SessionLocal() as db:
                original_revisions = list(db.scalars(select(CoaRevision).where(
                    CoaRevision.coa_id == cid
                )))
            html = client.get(f"/coas/{cid}").text
            assert '<details class="coa-audit-history">' in html
            assert '<summary>Audit history (2 entries)</summary>' in html
            assert 'class="coa-audit-history" open' not in html
            assert "qa649_event_0" in html and "qa649_event_1" in html
            assert html.count("<details") >= 3
            assert html.count("original metadata") == 2
            with SessionLocal() as db:
                new_revisions = list(db.scalars(select(CoaRevision).where(
                    CoaRevision.coa_id == cid
                )))
                assert [r.id for r in new_revisions] == [r.id for r in original_revisions]
                assert db.get(Coa, cid).original_name == "original-report.pdf"
                assert len(db.get(Coa, cid).attachments) == 2
                assert db.get(CoaDefaultDocument645, cid) is None
        finally:
            _cleanup(stored)
