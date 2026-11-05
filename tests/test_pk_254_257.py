from app.pk_revision_delta257 import (
    Snapshot,changes,equivalent
)
from pydantic import ValidationError
import pytest


def test_v1_snapshots_and_multisets():
    dose={
        'planned_at':'2026-11-04T08:00:00',
        'amount_mg':2.0
    }

    current={
        'name':'A',
        'half_life_hours':120.,
        'absorption_half_life_hours':12.,
        'doses':[dose,dose]
    }

    target={
        **current,
        'doses':[dose]
    }

    assert changes(current,target)['removed']==1
    assert not equivalent(current,target)
    assert equivalent(current,current)

    raw={
        **target,
        'compound_id':1
    }

    assert Snapshot.model_validate(raw).format_version==1

    with pytest.raises(ValidationError):
        Snapshot.model_validate({
            **raw,
            'format_version':2
        })

    with pytest.raises(ValidationError):
        Snapshot.model_validate({
            **raw,
            'half_life_hours':float('nan')
        })
