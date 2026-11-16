"""Release 646: accessible COA test-category dropdown and safe custom labels."""
import io
from uuid import uuid4

from fastapi.testclient import TestClient

from app.coa_test_types646 import COA_TEST_TYPE_GROUPS, COA_TEST_TYPE_VALUES
from app.db import SessionLocal
from app.main import app
from app.models import Coa, CoaAttachment


def _coa():
    with SessionLocal() as db:
        c = Coa(lab_name="Test type picker 646", stored_name=f"metadata-only-646-{uuid4().hex}")
        db.add(c)
        db.commit()
        return c.id


def _upload(client, cid, label):
    result = client.post(
        f"/coas/{cid}/attachments",
        files=[("files", ("assay646.pdf", io.BytesIO(b"%PDF-1.4\nCOA646\n"), "application/pdf"))],
        data={"test_type": label},
        follow_redirects=False,
    )
    assert result.status_code == 303
    with SessionLocal() as db:
        record = db.get(Coa, cid)
        assert len(record.attachments) == 1
        return record.attachments[0].id


def test_646_catalog_has_distinct_meaningful_peptide_and_oil_test_types():
    entries = [value for _, options in COA_TEST_TYPE_GROUPS for value, _ in options]
    assert len(entries) == len(set(entries))
    assert COA_TEST_TYPE_VALUES == frozenset(entries)
    assert {
        "Purity", "Identity", "Endotoxin", "Sterility", "Microbial screening",
        "Heavy metals", "TFA", "pH", "CHNS", "Fentanyl", "HGH dimer",
        "BA/BB", "Concentration", "Net peptide content",
    } <= COA_TEST_TYPE_VALUES


def test_646_compact_picker_renders_groups_and_preserves_unknown_historical_label():
    with TestClient(app) as client:
        cid = _coa()
        aid = _upload(client, cid, "Legacy odd-test 646")
        response = client.get(f"/coas/{cid}")
        assert response.status_code == 200
        html = response.text
        assert '<optgroup label="Core analysis">' in html
        assert '<optgroup label="Safety &amp; contamination">' in html
        assert '<optgroup label="Specialized analysis">' in html
        assert 'value="BA/BB"' in html
        assert 'value="TFA"' in html
        assert 'value="__custom__"' in html
        assert 'Existing: Legacy odd-test 646' in html
        assert 'value="Legacy odd-test 646" selected' in html
        assert 'data-coa-test-type-select' in html
        assert 'data-coa-test-type-form' in html
        assert 'tracker-coa-types646.js' in html
        assert 'name="custom_test_type"' in html
        assert f'/coas/{cid}/attachments/{aid}/test-type' in html


def test_646_dropdown_update_and_explicit_custom_mode_validated():
    with TestClient(app) as client:
        cid = _coa()
        aid = _upload(client, cid, "Purity")
        endpoint = f"/coas/{cid}/attachments/{aid}/test-type"
        assert client.post(endpoint, data={"test_type": "BA/BB"},
                           follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, aid).test_type == "BA/BB"

        # The custom sentinel is never saved literally; an empty entry fails.
        assert client.post(endpoint, data={"test_type": "__custom__"},
                           follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, aid).test_type == "BA/BB"

        assert client.post(endpoint, data={
            "test_type": "__custom__", "custom_test_type": "  Oil assay: related substances  ",
        }, follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, aid).test_type == "Oil assay: related substances"

        assert client.post(endpoint, data={
            "test_type": "__custom__", "custom_test_type": "x" * 121,
        }, follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, aid).test_type == "Oil assay: related substances"


def test_646_custom_upload_and_legacy_post_remain_compatible():
    with TestClient(app) as client:
        cid = _coa()
        response = client.post(
            f"/coas/{cid}/attachments",
            files=[("files", ("oil646.pdf", io.BytesIO(b"%PDF-1.4\nOIL646"), "application/pdf"))],
            data={"test_type": "__custom__", "custom_test_type": "  Oil vehicle analysis  "},
            follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            record = db.get(Coa, cid)
            assert len(record.attachments) == 1
            assert record.attachments[0].test_type == "Oil vehicle analysis"
        # Existing direct/API form submissions remain valid and trimmed.
        aid = record.attachments[0].id
        assert client.post(
            f"/coas/{cid}/attachments/{aid}/test-type",
            data={"test_type": "  Identity  "}, follow_redirects=False,
        ).status_code == 303
        with SessionLocal() as db:
            assert db.get(CoaAttachment, aid).test_type == "Identity"
