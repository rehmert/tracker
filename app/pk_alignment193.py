"""Shared sampling grid for comparable PK sensitivity curves."""
from .pk_metrics181 import resolution


def shared_step(half_life_hours):
    """Keep every variant on one sampling grid."""
    return min(
        resolution(half_life_hours*f)
        for f in (.75,1.,1.25)
    )


def validate_alignment(curves):
    if not curves:
        raise ValueError('No curves supplied')

    reference=[
        r['at'] for r in curves[0]
    ]

    if (
        not reference
        or any(
            [r['at'] for r in curve]!=reference
            for curve in curves[1:]
        )
    ):
        raise ValueError(
            'Sensitivity timelines are not identical'
        )

    return reference
