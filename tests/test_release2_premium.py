from datetime import datetime, timedelta
from app.sparklines import sparkline


def test_sparkline_needs_two_points():
    now = datetime(2026, 10, 26)
    assert sparkline([], 'Weight', now=now) == ''
    assert sparkline([(now, 10)], 'Weight', now=now) == ''


def test_sparkline_escapes_label_and_stays_in_bounds():
    now = datetime(2026, 10, 26)
    svg = sparkline([(now - timedelta(days=3), 80), (now, 70)], '<weight>', now=now)
    assert 'aria-label="&lt;weight&gt; trend' in svg
    assert '<polyline' in svg
    assert '6.0,8.0' in svg


def test_sparkline_excludes_old_values():
    now = datetime(2026, 10, 26)
    assert sparkline([(now - timedelta(days=60), 100), (now, 90)], 'Weight', now=now) == ''
