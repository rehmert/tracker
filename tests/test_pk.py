from datetime import datetime, timedelta
from app.pk import exposure_at, series, profile

def test_absorption_and_decay():
    t = datetime(2026, 1, 1)
    assert exposure_at(t, [(t, 5)], 120, 12) == 0
    assert 0 < exposure_at(t + timedelta(hours=24), [(t, 5)], 120, 12) < 5
    assert exposure_at(t + timedelta(days=20), [(t, 5)], 120, 12) < 1

def test_superposition_and_no_future_dose_leak():
    t = datetime(2026, 1, 1)
    first = exposure_at(t+timedelta(days=2), [(t, 5)], 120, 12)
    assert abs(exposure_at(t+timedelta(days=2), [(t, 5),(t, 5)], 120, 12) - 2*first) < 1e-9
    assert exposure_at(t, [(t+timedelta(days=1), 5)], 120, 12) == 0

def test_scenario_series_separation():
    t = datetime(2026, 1, 1)
    rows=series(t,t+timedelta(days=3),[(t,5)],[(t+timedelta(days=1),2)],120,12)
    assert rows[0]['actual'] == rows[0]['planned']
    assert rows[-1]['planned'] > rows[-1]['actual']

def test_profiles():
    assert profile('Tirzepatide') == (120,12)
    assert profile('unknown') is None
