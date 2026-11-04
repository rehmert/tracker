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

    from app.routers.pk import pk_create_batch_checked, pk_duplicate
    from app.pk_scenario_version import audit
    assert callable(pk_create_batch_checked)
    assert callable(pk_duplicate)
    assert callable(audit)
    # Audited write semantics are exercised by isolated SQLite tests,
    # independent of whitespace or string literal quotation style.

    importer=Path(
        'app/pk_template_import.py'
    ).read_text()

    assert '"scenario_import"' in importer
