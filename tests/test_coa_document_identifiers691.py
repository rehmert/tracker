"""Release 691: independently persisted, printable COA document identifiers.

These tests use the disposable pytest TRACKER_DATA_DIR, not either live host.
"""
from __future__ import annotations

import io
import sqlite3
from pathlib import Path
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
