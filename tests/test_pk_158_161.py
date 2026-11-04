from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
import pytest
from app.pk_guarded_edit161 import CheckedEdit


def test_invalid_edit_rejected():
    with pytest.raises(ValidationError):
        CheckedEdit(
            dose_id=1,
            planned_at=datetime(2026,11,4),
            amount_mg=0,
            expected_version='a'*64
        )


def test_lock_and_audit_contract():
    s=Path('app/pk_guarded_edit161.py').read_text()
    assert 'BEGIN IMMEDIATE' in s
    assert 'guarded_dose_update' in s
    assert 'ver.check(db,obj,data.expected_version)' in s
