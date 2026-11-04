from pathlib import Path
from fastapi import HTTPException
import pytest
from app.pk_scenario_integrity145 import required


def test_required_revision():
    with pytest.raises(HTTPException) as exc:
        required(None,object(),None)

    assert exc.value.status_code==428


def test_checked_batch_and_audit_contract():
    routes=Path('app/routers/pk.py').read_text()

    assert 'create-batch-checked' in routes
    assert '"scenario_duplicate"' in routes
    assert '"bulk_create"' in routes

    importer=Path(
        'app/pk_template_import.py'
    ).read_text()

    assert '"scenario_import"' in importer
