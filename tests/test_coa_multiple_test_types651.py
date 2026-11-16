"""Release 651: one COA document can report many independent tests.

The shared pytest conftest provides a disposable database per worker. No live
DEV/PROD data and no direct file migration are touched by this suite.
"""
from uuid import uuid4
from pathlib import Path
import io

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.coa_multitypes651 import PREFIX, CODEBOOK, decode, encode, from_selection
from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment, CoaDefaultDocument645, CoaRevision
from app.attachment_files400 import attachment_directory400


def _coa(*, initial=False):
    token = uuid4().hex
    original = f"qa651-original-{token}.pdf"
    with SessionLocal() as db:
        coa = Coa(
            lab_name="QA651 " + token,
            stored_name=original if initial else "metadata-" + token,
            original_name="combined-original.pdf" if initial else "",
            content_type="application/pdf" if initial else "",
            size_bytes=20 if initial else 0,
            sha256="a" * 64 if initial else "",
        )
        db.add(coa)
        db.commit()
        cid = coa.id
    if initial:
        (attachment_directory400("coa") / original).write_bytes(b"%PDF-1.4\nqa651\n")
    return cid, original if initial else None


def _upload(client, cid, label="Purity"):
    response = client.post(
        f"/coas/{cid}/attachments",
        data={"test_type": label},
        files={"files": ("test651.pdf", io.BytesIO(b"%PDF-1.4\nqa651"), "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with SessionLocal() as db:
        record = db.get(Coa, cid)
        item = record.attachments[-1]
        return item.id, item.stored_name


def _multi_form(key: str, before: str, selections: tuple[str, ...], custom=""):
    # Multipart-equivalent form can repeat checkbox keys; the required hidden
    # empty sentinel means every document is represented even when unchecked.
    return [
        (f"original_test_type_{key}", before),
        (f"custom_test_type_{key}", custom),
        (f"test_types_{key}", ""),
        *[(f"test_types_{key}", label) for label in selections],
    ]


def _post_multi(client, cid, rows, accept=True):
    # Starlette multipart parser reliably retains duplicate field keys.
    files = [(name, (None, value)) for row in rows for name, value in row]
    return client.post(
        f"/coas/{cid}/attachments/test-types",
        files=files,
        headers={"Accept": "application/json"} if accept else {},
        follow_redirects=False,
    )


def _cleanup(*names):
    directory = attachment_directory400("coa")
    for name in names:
        if name:
            (directory / name).unlink(missing_ok=True)


def test_651_stable_codebook_and_unmodified_legacy_labels():
    assert len(CODEBOOK) == len(set(CODEBOOK)) == 24
    assert decode(None) == decode("") == []
    assert decode("Purity") == ["Purity"]
    assert encode(["Purity"]) == "Purity"
    assert decode("Historical unknown assay") == ["Historical unknown assay"]
    assert decode("Purity & identity") == ["Purity & identity"]
    assert decode(encode([])) == []
    selected = ["Purity", "Identity", "Endotoxin", "Sterility"]
    encoded = encode(selected)
    assert encoded.startswith(PREFIX)
    assert len(encoded) <= 120
    assert decode(encoded) == selected
    assert len(encode(list(CODEBOOK))) <= 120
    assert decode(encode(list(CODEBOOK))) == list(CODEBOOK)
    assert decode(encode(["Identity", "Hormone panel by LC-MS"])) == [
        "Identity", "Hormone panel by LC-MS",
    ]


def test_651_invalid_duplicate_or_forged_multiselections_rejected():
    import pytest
    for selections in (
        ["Identity", "Identity"],
        ["Purity", "Unrecognized forged value"],
        ["Purity", "Identity", "Unknown-1", "Unknown-2"],
    ):
        with pytest.raises(ValueError):
            from_selection(selections, "")
    with pytest.raises(ValueError):
        encode(["Purity", "x" * 121])
    with pytest.raises(ValueError):
        from_selection(["Identity"], "y" * 121)


def test_651_multiple_types_persist_in_one_file_without_changing_default():
    with TestClient(app) as client:
        cid, _ = _coa()
        aid, stored = _upload(client, cid)
        try:
            page = client.get(f"/coas/{cid}").text
            assert f'name="test_types_{aid}"' in page
            assert f'name="original_test_type_{aid}" value="Purity"' in page
            assert "Save all test types" in page
            resp = _post_multi(client, cid, [
                _multi_form(str(aid), "Purity", ("Purity", "Identity", "Endotoxin"))
            ])
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["updated"] == 1
            stored_value = data["types"][str(aid)]
            assert decode(stored_value) == ["Purity", "Identity", "Endotoxin"]
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                assert len(coa.attachments) == 1
                assert decode(coa.attachments[0].test_type) == [
                    "Purity", "Identity", "Endotoxin",
                ]
                assert db.get(CoaDefaultDocument645, cid) is None
            after = client.get(f"/coas/{cid}").text
            for name in ("Purity", "Identity", "Endotoxin"):
                assert f'value="{name}" form="coa-bulk-test-types" data-coa-multi-choice checked' in after
            assert "test651.pdf" in after
            assert "Purity · Identity · Endotoxin" in after
        finally:
            _cleanup(stored)


def test_651_atomic_stale_duplicate_and_cross_record_rejection():
    with TestClient(app) as client:
        cid, _ = _coa()
        oid, _ = _coa()
        a, a_stored = _upload(client, cid, "Purity")
        b, b_stored = _upload(client, cid, "Identity")
        other, other_stored = _upload(client, oid, "Sterility")
        try:
            valid = [
                _multi_form(str(a), "Purity", ("Purity", "Identity")),
                _multi_form(str(b), "Identity", ("Identity", "Endotoxin")),
            ]
            stale = [
                valid[0],
                _multi_form(str(b), "Wrong historic label", ("Endotoxin",)),
            ]
            for rows, expected in (
                (stale, 409),
                (valid + [_multi_form(str(other), "Sterility", ("Purity",))], 409),
                ([valid[0] + [(f"test_types_{a}", "Identity")], valid[1]], 400),
                ([valid[0], _multi_form(str(b), "Identity", ("Fraud",))], 400),
            ):
                response = _post_multi(client, cid, rows)
                assert response.status_code == expected, response.text
            with SessionLocal() as db:
                assert db.get(CoaAttachment, a).test_type == "Purity"
                assert db.get(CoaAttachment, b).test_type == "Identity"
                assert db.get(CoaAttachment, other).test_type == "Sterility"
                assert list(db.scalars(select(CoaRevision).where(
                    CoaRevision.coa_id == cid,
                    CoaRevision.event == "attachment_test_types_bulk",
                ))) == []
            ok = _post_multi(client, cid, valid)
            assert ok.status_code == 200
            assert ok.json()["updated"] == 2
            with SessionLocal() as db:
                assert decode(db.get(CoaAttachment, a).test_type) == ["Purity", "Identity"]
                assert decode(db.get(CoaAttachment, b).test_type) == ["Identity", "Endotoxin"]
                assert len(list(db.scalars(select(CoaRevision).where(
                    CoaRevision.coa_id == cid, CoaRevision.event == "attachment_test_types_bulk"
                )))) == 1
        finally:
            _cleanup(a_stored, b_stored, other_stored)


def test_651_legacy_first_file_can_have_multiple_tests_without_duplicate_pdf():
    with TestClient(app) as client:
        cid, original = _coa(initial=True)
        try:
            response = _post_multi(client, cid, [
                _multi_form("original", "", ("Purity", "Identity", "Endotoxin"))
            ])
            assert response.status_code == 200, response.text
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                mirrors = [a for a in coa.attachments if a.stored_name == original]
                assert len(mirrors) == 1
                assert decode(mirrors[0].test_type) == ["Purity", "Identity", "Endotoxin"]
                assert db.get(CoaDefaultDocument645, cid) is None
            html = client.get(f"/coas/{cid}").text
            assert html.count(f'href="/coas/{cid}/original-file"') == 1
            assert client.get(f"/coas/{cid}/file").status_code == 200
        finally:
            _cleanup(original)


def test_651_combined_types_upload_and_custom_type_persist():
    with TestClient(app) as client:
        cid, _ = _coa()
        try:
            response = client.post(
                f"/coas/{cid}/attachments",
                files=[
                    ("test_types", (None, "")),
                    ("test_types", (None, "Purity")),
                    ("test_types", (None, "Identity")),
                    ("test_types", (None, "Endotoxin")),
                    ("custom_test_type", (None, "Assay 651")),
                    ("files", ("combined651.pdf", io.BytesIO(
                        b"%PDF-1.4\ncombined651\n"), "application/pdf")),
                ],
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                assert len(coa.attachments) == 1
                att = coa.attachments[0]
                stored = att.stored_name
                assert decode(att.test_type) == [
                    "Purity", "Identity", "Endotoxin", "Assay 651",
                ]
            assert "combined651.pdf" in client.get(f"/coas/{cid}").text
        finally:
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                _cleanup(*(a.stored_name for a in coa.attachments))


def test_651_no_js_form_fallback_and_deselect_all_types():
    with TestClient(app) as client:
        cid, _ = _coa()
        aid, stored = _upload(client, cid)
        try:
            response = _post_multi(
                client, cid,
                [_multi_form(str(aid), "Purity", ("Purity", "Identity"))],
                accept=False,
            )
            assert response.status_code == 303
            assert "#test-documents" in response.headers["location"]
            with SessionLocal() as db:
                old = db.get(CoaAttachment, aid).test_type
                assert decode(old) == ["Purity", "Identity"]
            # Only the blank hidden test_types field is submitted: no selected
            # boxes means unclassified, not a missing document row.
            clear = _post_multi(
                client, cid, [_multi_form(str(aid), old, ())],
            )
            assert clear.status_code == 200, clear.text
            assert clear.json()["updated"] == 1
            with SessionLocal() as db:
                assert db.get(CoaAttachment, aid).test_type == ""
        finally:
            _cleanup(stored)


def test_651_no_navigation_save_and_editable_native_fallback_contract():
    source = (Path(__file__).resolve().parents[1] /
              "app/static/js/tracker-coa-multi651.js").read_text()
    assert 'new FormData(form)' in source
    assert 'fetch(form.action' in source
    assert 'credentials: "same-origin"' in source
    assert 'event.preventDefault()' in source
    assert 'data-coa-original-type' in source
    assert 'window.location' not in source
    assert 'location.reload' not in source
    legacy = (Path(__file__).resolve().parents[1] /
              "app/static/js/tracker-coa-types647.js").read_text()
    # External form-associated inputs are not DOM descendants of the
    # empty form tag, so detect the new editor globally, not inside it.
    assert 'document.querySelector("[data-coa-multi651]")' in legacy
    assert 'form.querySelector("[data-coa-multi651]")' not in legacy
