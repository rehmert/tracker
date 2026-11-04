from datetime import datetime
from pathlib import Path

from app.pk_staged_schedule import (
    StagedInput,Stage,project
)


def test_stage_boundaries_and_fractional_days():
    data=StagedInput(
        start_at=datetime(2026,11,4,8),
        stages=[
            Stage(
                amount_mg=1,
                count=2,
                interval_days=.5
            ),
            Stage(
                amount_mg=2,
                count=2,
                interval_days=1
            )
        ]
    )

    rows=project(data)

    assert [
        x['amount_mg'] for x in rows
    ]==[1,1,2,2]

    assert rows[1]['planned_at'].endswith(
        '20:00:00'
    )

    assert len({
        x['planned_at'] for x in rows
    })==4


def test_staged_interface():
    html=Path('app/templates/pk.html').read_text()
    assert 'pkStageReplace' in html
