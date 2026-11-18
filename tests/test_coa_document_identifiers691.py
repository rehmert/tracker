"""Release 691: independently persisted, printable COA document identifiers.

These tests use the disposable pytest TRACKER_DATA_DIR, not either live host.
"""
from __future__ import annotations

import io
import os
import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select

from app.db import SessionLocal
from app.main import app
from app.migrations import migrate
from app.models import Coa, CoaAttachment, CoaRevision, CoaDefaultDocument645


def _coa(original=True):
    token = uuid4().hex
    with SessionLocal() as db:
        coa = Coa(
            lab_name="QA691 Laboratory",
            original_name="original-691.pdf" if original else "",
            stored_name=("qa691-" + token + ".pdf") if original else "metadata-" + token,
            content_type="application/pdf" if original else "",
            size_bytes=20 if original else 0,
            sha256="a" * 64 if original else "",
            job_id="0001-ROOT", verify_code="VERIFY-ROOT",
        )
        db.add(coa)
        db.flush()
        cid = coa.id
        for index in (1, 2):
            db.add(CoaAttachment(
                coa_id=cid, test_type="Purity" if index == 1 else "Identity",
                original_name=f"lab-test-{index}.pdf",
                stored_name=f"qa691-{uuid4().hex}.pdf",
                content_type="application/pdf", size_bytes=20, sha256="b" * 64,
                job_id=f"000{index}-TASK", verify_code=f"VERIFY-{index}",
            ))
        db.commit()
        return cid


def _rows(db, cid):
    coa = db.get(Coa, cid)
    return coa, list(coa.attachments)


def _form(coa, attachments):
    out = {}
    if coa.original_name:
        out.update({
            "job_id_original": coa.job_id,
            "verify_code_original": coa.verify_code,
            "original_job_id_original": coa.job_id,
            "original_verify_code_original": coa.verify_code,
        })
    for item in attachments:
        key = str(item.id)
        out.update({
            f"job_id_{key}": item.job_id,
            f"verify_code_{key}": item.verify_code,
            f"original_job_id_{key}": item.job_id,
            f"original_verify_code_{key}": item.verify_code,
        })
    return out


def _save(client, cid, data):
    return client.post(
        f"/coas/{cid}/attachments/identifiers", data=data,
        headers={"Accept": "application/json"},
    )


def test_691_additive_migration_is_idempotent_and_preserves_old_values(tmp_path):
    dbpath = tmp_path / "legacy-coa691.sqlite"
    connection = sqlite3.connect(dbpath)
    try:
        connection.executescript("""
            CREATE TABLE coas (
                id INTEGER PRIMARY KEY, job_id VARCHAR(120),
                verify_code VARCHAR(120)
            );
            INSERT INTO coas VALUES (1, '000OLD', 'VER-OLD');
            CREATE TABLE coa_attachments (
                id INTEGER PRIMARY KEY, coa_id INTEGER,
                test_type VARCHAR(120), original_name TEXT, stored_name TEXT
            );
            INSERT INTO coa_attachments VALUES (10, 1, 'Purity',
                'original.pdf', 'stored.pdf');
        """)
        connection.commit()
    finally:
        connection.close()
    engine = create_engine("sqlite:///" + str(dbpath))
    migrate(engine)
    migrate(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("coa_attachments")}
    assert {"job_id", "verify_code"} <= columns
    with engine.connect() as conn:
        original = conn.exec_driver_sql(
            "SELECT job_id, verify_code FROM coas WHERE id=1"
        ).one()
        added = conn.exec_driver_sql(
            "SELECT test_type, original_name, stored_name, job_id, verify_code "
            "FROM coa_attachments WHERE id=10"
        ).one()
    assert tuple(original) == ("000OLD", "VER-OLD")
    assert tuple(added) == ("Purity", "original.pdf", "stored.pdf", "", "")


def test_691_table_shows_independent_original_and_additional_identifiers():
    with TestClient(app) as client:
        cid = _coa()
        with SessionLocal() as db:
            coa, items = _rows(db, cid)
            first, second = items
            key_first, key_second = first.id, second.id
        response = client.get(f"/coas/{cid}")
        assert response.status_code == 200
        html = response.text
        assert '<th>Task number</th>' in html
        assert '<th>Verification number</th>' in html
        assert 'form="coa-document-identifiers691"' in html
        assert 'name="job_id_original"' in html
        assert 'name="verify_code_original"' in html
        assert 'name="job_id_original" form="coa-document-identifiers691" value="0001-ROOT"' in html
        assert 'name="verify_code_original" form="coa-document-identifiers691" value="VERIFY-ROOT"' in html
        assert f'name="job_id_{key_first}" form="coa-document-identifiers691" value="0001-TASK"' in html
        assert f'name="verify_code_{key_second}" form="coa-document-identifiers691" value="VERIFY-2"' in html
        assert "Save task / verification numbers" in html
        assert "Verification links will be added" in html


def test_691_per_document_edit_atomic_independent_no_type_or_review_mutation():
    with TestClient(app) as client:
        cid = _coa()
        with SessionLocal() as db:
            coa, items = _rows(db, cid)
            form = _form(coa, items)
            first_id, second_id = items[0].id, items[1].id
            original_types = [item.test_type for item in items]
        form["job_id_original"] = "ROOT-0002"
        form["verify_code_original"] = "ROOT-VERIFY-0002"
        form[f"job_id_{first_id}"] = "T-0001"
        form[f"verify_code_{first_id}"] = "v:2026/ABC-1"
        form[f"job_id_{second_id}"] = "Task-B"
        form[f"verify_code_{second_id}"] = "00000007"
        resp = _save(client, cid, form)
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True, "error": "", "updated": 3}
        with SessionLocal() as db:
            coa, items = _rows(db, cid)
            assert (coa.job_id, coa.verify_code) == ("ROOT-0002", "ROOT-VERIFY-0002")
            assert [(i.job_id, i.verify_code) for i in items] == [
                ("T-0001", "v:2026/ABC-1"), ("Task-B", "00000007")
            ]
            assert [i.test_type for i in items] == original_types
            assert coa.verification_status == "unreviewed"
            assert db.get(CoaDefaultDocument645, cid) is None
            changes = list(db.scalars(select(CoaRevision).where(
                CoaRevision.coa_id == cid,
                CoaRevision.event == "document_identifiers_bulk",
            )))
            assert len(changes) == 1
            unchanged = _save(client, cid, _form(coa, items))
            assert unchanged.json()["updated"] == 0
        assert "00000007" in client.get(f"/coas/{cid}").text


def test_691_reject_stale_forged_duplicate_oversize_without_partial_writes():
    with TestClient(app) as client:
        cid = _coa()
        other = _coa()
        with SessionLocal() as db:
            coa, items = _rows(db, cid)
            original = _form(coa, items)
            foreign = _rows(db, other)[1][0].id
            first = items[0].id
            old_values = [(v.job_id, v.verify_code) for v in items]
        cases = [
            ({**original, f"original_verify_code_{first}": "WRONG"}, 409),
            ({**original, f"job_id_{foreign}": "CROSS-COA"}, 409),
            ({**original, f"job_id_{first}": "X" * 121}, 400),
            ({**original, f"verify_code_{first}": "BAD\nNEWLINE"}, 400),
        ]
        for form, status in cases:
            response = _save(client, cid, form)
            assert response.status_code == status, response.text
            assert response.json()["ok"] is False
        double = [
            (key, (None, value)) for key, value in original.items()
        ] + [(f"job_id_{first}", (None, "DUPLICATE"))]
        response = client.post(
            f"/coas/{cid}/attachments/identifiers",
            files=double,
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 400, response.text
        with SessionLocal() as db:
            current = db.get(Coa, cid)
            assert (current.job_id, current.verify_code) == ("0001-ROOT", "VERIFY-ROOT")
            assert [(v.job_id, v.verify_code) for v in current.attachments] == old_values
            assert list(db.scalars(select(CoaRevision).where(
                CoaRevision.coa_id == cid,
                CoaRevision.event == "document_identifiers_bulk",
            ))) == []


def test_691_metadata_only_record_does_not_render_fake_original_document():
    with TestClient(app) as client:
        cid = _coa(original=False)
        html = client.get(f"/coas/{cid}").text
        assert 'name="job_id_original" form="coa-document-identifiers691"' not in html
        assert "lab-test-1.pdf" in html



def test_691_legacy_root_mirror_keeps_one_table_row_and_synced_identifiers():
    with TestClient(app) as client:
        cid = _coa()
        # Saving a test selection for the first file creates the normal
        # compatibility mirror without copying the original attachment.
        # The bulk endpoint is deliberately fail-closed: all displayed
        # documents must be submitted, even if only the original changes.
        with SessionLocal() as db:
            coa, extra_documents = _rows(db, cid)
            assert len(extra_documents) == 2
            fields = [
                ("test_types_original", (None, "")),
                ("test_types_original", (None, "Purity")),
                ("custom_test_type_original", (None, "")),
                ("original_test_type_original", (None, "")),
            ]
            for doc in extra_documents:
                key = str(doc.id)
                fields.extend([
                    (f"test_types_{key}", (None, "")),
                    (f"test_types_{key}", (None, doc.test_type)),
                    (f"custom_test_type_{key}", (None, "")),
                    (f"original_test_type_{key}", (None, doc.test_type)),
                ])
        response = client.post(
            f"/coas/{cid}/attachments/test-types",
            files=fields,
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["updated"] == 1
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            mirrors = [x for x in coa.attachments if x.stored_name == coa.stored_name]
            assert len(mirrors) == 1
            mirror = mirrors[0]
            assert (mirror.job_id, mirror.verify_code) == ("0001-ROOT", "VERIFY-ROOT")
            form = _form(coa, [x for x in coa.attachments if x.id != mirror.id])
        form["job_id_original"] = "ORIGINAL-ALPHA"
        form["verify_code_original"] = "Verify-ZERO"
        saved = _save(client, cid, form)
        assert saved.status_code == 200, saved.text
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            mirror = next(x for x in coa.attachments if x.stored_name == coa.stored_name)
            assert (coa.job_id, coa.verify_code) == ("ORIGINAL-ALPHA", "Verify-ZERO")
            assert (mirror.job_id, mirror.verify_code) == ("ORIGINAL-ALPHA", "Verify-ZERO")
            # Root file shown once even though its metadata is mirrored.
            html = client.get(f"/coas/{cid}").text
            assert html.count(f'href="/coas/{cid}/original-file"') == 1
            assert f'name="job_id_{mirror.id}"' not in html


def test_691_native_form_redirect_and_html_escaping():
    with TestClient(app) as client:
        cid = _coa()
        with SessionLocal() as db:
            coa, docs = _rows(db, cid)
            data = _form(coa, docs)
            data[f"verify_code_{docs[0].id}"] = "<example & verify>"
        response = client.post(
            f"/coas/{cid}/attachments/identifiers",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        assert "#test-documents" in response.headers["location"]
        html = client.get(f"/coas/{cid}").text
        assert "&lt;example &amp; verify&gt;" in html
        assert 'value="<example & verify>"' not in html

def test_691_single_upload_identifiers_and_multifile_rejection():
    with TestClient(app) as client:
        cid = _coa()
        invalid = client.post(
            f"/coas/{cid}/attachments",
            data={"job_id": "T-1", "verify_code": "V-1"},
            files=[
                ("files", ("first.pdf", io.BytesIO(b"%PDF-1.4\nfirst"), "application/pdf")),
                ("files", ("second.pdf", io.BytesIO(b"%PDF-1.4\nsecond"), "application/pdf")),
            ],
            follow_redirects=False,
        )
        assert invalid.status_code == 303
        assert "err=" in invalid.headers["location"]
        with SessionLocal() as db:
            assert len(db.get(Coa, cid).attachments) == 2
        response = client.post(
            f"/coas/{cid}/attachments",
            data={"job_id": "Task-000123", "verify_code": "V-0098", "test_type": "Purity"},
            files={"files": ("new.pdf", io.BytesIO(b"%PDF-1.4\nsingle"), "application/pdf")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            coa = db.get(Coa, cid)
            new = coa.attachments[-1]
            assert (new.job_id, new.verify_code) == ("Task-000123", "V-0098")
            assert (coa.job_id, coa.verify_code) == ("0001-ROOT", "VERIFY-ROOT")
            assert new.test_type == "Purity"
            stored = new.stored_name
        from app.attachment_files400 import attachment_directory400
        (attachment_directory400("coa") / stored).unlink(missing_ok=True)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_691_browser_form_association_and_mobile_document_table(width):
    with TestClient(app) as client:
        cid = _coa()
        html = client.get(f"/coas/{cid}").text
        start = html.index('<section id="test-documents">')
        stop = html.index("</section>", start) + len("</section>")
        fragment = html[start:stop]
        doc = (
            '<!doctype html><html><head><meta name="viewport" '
            'content="width=device-width,initial-scale=1"></head>'
            '<body><main id="main-content">' + fragment + '</main></body></html>'
        )
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
            )
            try:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.set_content(doc)
                page.add_style_tag(content=(
                    Path(__file__).resolve().parents[1] /
                    "app/static/css/tracker-coa-identifiers691.css"
                ).read_text())
                expect(page.get_by_role("columnheader", name="Task number")).to_be_visible()
                expect(page.get_by_role("columnheader", name="Verification number")).to_be_visible()
                expect(page.get_by_role("button", name="Save task / verification numbers")).to_be_visible()
                assert page.locator(".coa-document-table tbody tr").count() == 3
                values = page.evaluate("""() => {
                  const form = document.getElementById('coa-document-identifiers691');
                  return [...new FormData(form).entries()];
                }""")
                names = [name for name, value in values]
                assert len(names) == 12, values
                assert "job_id_original" in names
                assert "verify_code_original" in names
                assert all(not key.startswith("test_types") for key in names)
                assert page.locator('input[name="job_id_original"]').input_value() == "0001-ROOT"
                assert page.locator('input[name="verify_code_original"]').input_value() == "VERIFY-ROOT"
                # Horizontal scroll is intentional for a dense document table;
                # editable inputs remain visible via scrolling, never omitted.
                assert page.locator('.coa-identifier691-cell input[type="text"]').count() == 0
                assert page.locator('.coa-identifier691-cell input:not([type="hidden"])').count() == 6
            finally:
                browser.close()
