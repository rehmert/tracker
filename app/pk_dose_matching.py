"""Descriptive matching, never protocol attribution or dose advice."""


def candidates(planned, recorded, max_hours=24):
    pool = sorted(recorded)
    used = set()
    matches = []

    for when, amount in sorted(planned):
        eligible = [
            (abs((at - when).total_seconds()), i, mg)
            for i, (at, mg) in enumerate(pool)
            if i not in used
            and abs((at - when).total_seconds())
            <= max_hours * 3600
        ]

        if not eligible:
            continue

        seconds, index, mg = min(eligible)
        used.add(index)

        matches.append({
            'scheduled': when.isoformat(),
            'recorded': pool[index][0].isoformat(),
            'offset_hours': round(
                (
                    pool[index][0] - when
                ).total_seconds() / 3600,
                3,
            ),
            'amount_delta_mg': round(mg - amount, 5),
        })

    return {
        'candidate_matches': matches[:200],
        'unmatched_planned': len(planned) - len(matches),
        'unmatched_recorded': len(pool) - len(matches),
        'warning': (
            'Time-near candidates only; '
            'not protocol attribution.'
        ),
    }
