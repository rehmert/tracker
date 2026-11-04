from datetime import datetime,timedelta
import pytest
from fastapi import HTTPException
from app import pk
from app.pk_precision225 import bounded_step,refined_peak


def test_budget_rejects_excessive_work():
    with pytest.raises(HTTPException) as err:
        bounded_step(720,.5,501)
    assert err.value.status_code==413
    assert bounded_step(720,.5,100)>=.5


def test_refinement_improves_coarse_peak():
    start=datetime(2026,11,4)
    doses=[(start,3.)]
    rows=pk.series(start,start+timedelta(hours=24),[],doses,12,3,step_hours=12)
    refined=refined_peak(rows,doses,12,3)
    assert refined>max(row['planned'] for row in rows)
    assert refined<=3
