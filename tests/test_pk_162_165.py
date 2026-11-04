from datetime import datetime
from types import SimpleNamespace
from pydantic import ValidationError
import pytest

from app.pk_transform165 import (
    Transform,projected
)


def test_transform_preserves_record_identity():
    data=Transform(
        shift_hours=84,
        amount_multiplier=1.5,
        expected_version='a'*64
    )
    dose=SimpleNamespace(
        id=7,
        planned_at=datetime(2026,11,4,8),
        amount_mg=2
    )
    r=projected([dose],data)[0]
    assert r['id']==7
    assert r['amount_mg']==3
    assert r['planned_at']=='2026-11-07T20:00:00'


def test_invalid_multiplier():
    with pytest.raises(ValidationError):
        Transform(
            shift_hours=0,
            amount_multiplier=0,
            expected_version='a'*64
        )
