from datetime import date, timedelta
import random
import pytest
from app.routers.calendar import reconcile, calendar_day_sort_key

def reference_reconcile(planned, actual, today):
    """Match each recorded dose to at most one same-day planned occurrence.

    A matching record is displayed as 'recorded', while unmatched past
    projections are 'unrecorded' (not a clinical assertion of a missed dose).
    """
    result = {}
    for day in sorted(set(planned) | set(actual)):
        events = []
        recordings = list(actual.get(day, []))
        used = set()
        for p in planned.get(day, []):
            matched = next((idx for idx, a in enumerate(recordings)
                            if idx not in used and a['compound_id'] == p['compound_id']), None)
            if matched is not None:
                used.add(matched)
                # Preserve the source blend only when the matched recording
                # actually originated from a prepared blend.
                events.append(dict(
                    p, status='recorded',
                    actual_dose=recordings[matched]['dose'],
                    actual_blend_id=recordings[matched].get('blend_id'),
                ))
            else:
                status = 'unrecorded' if day < today else ('due' if day == today else 'upcoming')
                events.append(dict(p, status=status, actual_dose=None))
        for idx, a in enumerate(recordings):
            if idx not in used:
                events.append(dict(a, status='extra'))
        result[day] = sorted(events, key=calendar_day_sort_key)
    return result



@pytest.mark.parametrize("seed", range(20))
def test_reconciliation_parity(seed):
    rng = random.Random(seed)
    today = date(2026, 1, 1)
    planned, actual = {}, {}
    for offset in (-1, 0, 1):
        day = today + timedelta(days=offset)
        planned[day] = [dict(compound_id=rng.randrange(8), name="Compound", dose=str(i), protocol_item_id=i, dose_time="07:00") for i in range(60)]
        actual[day] = [dict(compound_id=rng.randrange(8), name="Compound", dose=str(i), blend_id=i if i % 2 else None, dose_time="08:00") for i in range(45)]
    assert reconcile(planned, actual, today) == reference_reconcile(planned, actual, today)
