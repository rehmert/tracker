from datetime import datetime,timedelta
from fastapi import HTTPException
import pytest
from app.pk_delta153 import delta


def test_delta_auc():
    t=datetime(2026,11,4,0)

    stamps=[
        (t+timedelta(hours=i)).isoformat()
        for i in (0,1,2)
    ]

    result=delta(
        stamps,[1,1,1],[2,2,2]
    )

    assert result['auc_delta']==2
    assert result['mean_delta']==1


def test_delta_rejects_misalignment():
    with pytest.raises(HTTPException):
        delta(
            ['2026-11-04T00:00:00'],
            [1],[2]
        )
