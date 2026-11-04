from datetime import datetime
from types import SimpleNamespace

from app.pk_model_history import capture, resolve
from app.pk_dose_matching import candidates
from app.pk_schedule_core import schedule_doses


def test_model_provenance_and_validation():
    compound = SimpleNamespace(name='Tirzepatide')
    original = capture(compound)
    assert original['half_life_hours'] > 0
    assert resolve(compound, original)[1] == 'saved'
    altered = dict(original, half_life_hours=100)
    assert resolve(compound, altered)[2]


def test_candidate_matching_is_one_to_one():
    at = datetime(2026, 11, 4, 8)
    result = candidates(
        [(at, 5), (at, 5)], [(at, 4)]
    )
    assert len(result['candidate_matches']) == 1
    assert result['unmatched_planned'] == 1


def test_canonical_interface():
    item = SimpleNamespace(
        compound_id=1,
        amount_value=5,
        amount_unit='mg',
        freq_count=3.5,
        freq_period='interval',
        start_week=1,
        end_week=None,
        dose_days='',
        dose_time='08:00',
    )
    protocol = SimpleNamespace(items=[item])
    anchor = datetime(2026, 11, 4).date()
    assert len(schedule_doses(protocol, 1, anchor, 7)) == 2
