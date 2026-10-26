from datetime import date
from app.forecasting import _estimate, forecast_inventory


def test_estimate_handles_no_history():
    assert _estimate(10, 0, 90, date(2026, 10, 26)) == (None, None)


def test_estimate_depletion():
    days, end = _estimate(10, 30, 90, date(2026, 10, 26))
    assert days == 30
    assert end == date(2026, 11, 25)


def test_invalid_history_window():
    try:
        forecast_inventory(None, window_days=45)
    except ValueError:
        pass
    else:
        raise AssertionError('Unsupported history window accepted')
