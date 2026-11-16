"""Release 652: configurable COA test catalog on isolated test databases."""
import io
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.coa_catalog652 import (
    PREFIX, catalog652, from_selection652, key652, seed_catalog652,
    selections652,
)
from app.coa_multitypes651 import CODEBOOK
from app.db import SessionLocal, engine
from app.main import app
from app.models import Coa, CoaAttachment, CoaTestType652


def _create_type(client):
    name = "Beer-Lambert AUC " + uuid4().hex[:10]
    response = client.post("/coa-test-types", data={
        "label": name, "group_name": "Core analysis",
    }, follow_redirects=False)
    assert response.status_code == 303
    with SessionLocal() as db:
        item = db.scalar(select(CoaTestType652).where(CoaTestType652.label == name))
        assert item is not None
        return item.id, name


def _coa():
    with SessionLocal() as db:
        c = Coa(lab_name="Catalog652", stored_name="metadata-" + uuid4().hex)
        db.add(c)
        db.commit()
        return c.id


def _upload(client, cid, selections):
    data = [("test_types", (None, ""))]
    data += [("test_types", (None, label)) for label in selections]
    data.append(("files", ("catalog652.pdf", io.BytesIO(b"%PDF-1.4\ncoa652"),
                           "application/pdf")))
    return client.post(f"/coas/{cid}/attachments", files=data, follow_redirects=False)


def _bulk(client, cid, aid, previous, checked):
    fields = [
        (f"original_test_type_{aid}", (None, previous)),
        (f"custom_test_type_{aid}", (None, "")),
        (f"test_types_{aid}", (None, "")),
        *[(f"test_types_{aid}", (None, v)) for v in checked],
    ]
    return client.post(
        f"/coas/{cid}/attachments/test-types", files=fields,
        headers={"Accept": "application/json"}, follow_redirects=False,
    )


def test_652_builtin_catalog_is_seeded_only_once_and_preserves_fixed_codes():
    with TestClient(app):
        with SessionLocal() as db:
            before = catalog652(db)
            builtin = [row for row in before if row.builtin_code is not None]
            assert len(builtin) == len(CODEBOOK) == 24
            assert {row.builtin_code for row in builtin} == set(CODEBOOK)
            ids = {row.builtin_code: row.id for row in builtin}
        seed_catalog652(engine)
        with SessionLocal() as db:
            assert {row.builtin_code: row.id for row in catalog652(db)
                    if row.builtin_code} == ids


def test_652_create_rename_regroup_deactivate_and_preserve_existing_documents():
    with TestClient(app) as client:
        assert client.get("/coa-test-types").status_code == 200
        custom_id, original_name = _create_type(client)
        token = f"@652:{custom_id}"
        cid = _coa()
        assert _upload(client, cid, ["Purity", token]).status_code == 303
        with SessionLocal() as db:
            attachment = db.get(Coa, cid).attachments[-1]
            aid, filename = attachment.id, attachment.stored_name
            stored = attachment.test_type
            assert stored.startswith(PREFIX)
            assert selections652(stored) == ["Purity", token]
        from app.attachment_files400 import attachment_directory400
        try:
            before = client.get(f"/coas/{cid}").text
            assert original_name in before
            assert f'value="{token}"' in before
            assert f'name="test_types_{aid}"' in before
            assert "Purity · " + original_name in before
            renamed = original_name + " updated"
            response = client.post(f"/coa-test-types/{custom_id}/edit", data={
                "label": renamed, "group_name": "Specialized analysis",
            }, follow_redirects=False)
            assert response.status_code == 303
            with SessionLocal() as db:
                assert db.get(CoaAttachment, aid).test_type == stored
            html = client.get(f"/coas/{cid}").text
            assert renamed in html
            assert "Purity · " + renamed in html
            assert f'value="{token}"' in html

            disabled = client.post(
                f"/coa-test-types/{custom_id}/toggle", follow_redirects=False)
            assert disabled.status_code == 303
            with SessionLocal() as db:
                assert db.get(CoaTestType652, custom_id).active is False
            html = client.get(f"/coas/{cid}").text
            assert renamed + " (inactive)" in html
            assert f'value="{token}" form="coa-bulk-test-types" data-coa-multi-choice checked' in html
            assert _bulk(client, cid, aid, stored, ("Purity", token)).json()["updated"] == 0

            rejected = _upload(client, cid, ["Identity", token])
            assert rejected.status_code == 303
            with SessionLocal() as db:
                coa = db.get(Coa, cid)
                assert len(coa.attachments) == 1
                assert coa.attachments[0].test_type == stored

            removed = _bulk(client, cid, aid, stored, ("Purity",))
            assert removed.status_code == 200
            assert removed.json()["updated"] == 1
            forged = _bulk(client, cid, aid, "Purity", ("Purity", token))
            assert forged.status_code == 400
            with SessionLocal() as db:
                assert db.get(CoaAttachment, aid).test_type == "Purity"
        finally:
            (attachment_directory400("coa") / filename).unlink(missing_ok=True)


def test_652_reject_forged_and_duplicate_catalog_selections_without_mutations():
    with TestClient(app) as client:
        custom_id, name = _create_type(client)
        with SessionLocal() as db:
            items = catalog652(db)
        assert key652(next(row for row in items if row.id == custom_id)) == f"@652:{custom_id}"
        for checked in (
            ["Purity", "Purity"],
            ["Purity", "@652:999999999"],
            ["Purity", "Other custom forged"],
        ):
            try:
                from_selection652(checked, "", items)
            except ValueError:
                pass
            else:
                raise AssertionError("Forged or duplicate COA selection accepted")
        assert from_selection652(["Identity"], "", items) == "Identity"
        assert selections652("Historic lab-specific test") == ["Historic lab-specific test"]
        response = client.post("/coa-test-types", data={
            "label": name.swapcase(), "group_name": "Core analysis",
        }, follow_redirects=False)
        assert response.status_code == 303
        with SessionLocal() as db:
            assert len(list(db.scalars(select(CoaTestType652).where(
                CoaTestType652.label.ilike(name)
            )))) == 1



def test_652_promotion_requires_genuine_scoped_receipt():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts/tracker_promote568.py"
    spec = importlib.util.spec_from_file_location("tracker_promote652", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sha = "b" * 40
    lines = [
        "QA_FULL_REQUIRED=0",
        "RELEASE_SCOPED_PREFLIGHT=PASSED",
        "FOCUSED_RELEASE_GATE=PASSED",
        "=== ISOLATED RESTORE VERIFICATION PASSED ===",
        " TRACKER RELEASE DEPLOYMENT SUCCESS",
        "EXIT_STATUS=0",
        "DEV_QUALIFIED_COMMIT=" + sha,
    ]
    module.verified_log("\n".join(lines) + "\n", sha)
    import pytest
    with pytest.raises(module.ReleaseError):
        module.verified_log(
            "\n".join(row for row in lines if row != "RELEASE_SCOPED_PREFLIGHT=PASSED") + "\n",
            sha,
        )
