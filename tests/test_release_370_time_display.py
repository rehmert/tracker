from datetime import datetime

from app.templating import dt, utc_dt, templates


def test_24h_eastern_display_preserves_timezone_semantics():
    assert dt(
        datetime(2026, 11, 4, 21, 7)
    ) == '2026-11-04 21:07 EST'

    assert utc_dt(
        datetime(2026, 11, 5, 2, 7)
    ) == '2026-11-04 21:07 EST'

    assert dt(
        datetime(2026, 7, 4, 21, 7)
    ) == '2026-07-04 21:07 EDT'

    rendered = templates.env.from_string(
        '{{ at|dt }}'
    ).render(at=datetime(2026, 11, 4, 0, 5))

    assert rendered == '2026-11-04 00:05 EST'
    assert ' AM ' not in rendered
    assert ' PM ' not in rendered
