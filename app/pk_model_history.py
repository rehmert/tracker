"""Versioned read-only PK assumptions; not validated serum PK."""
from math import isfinite
from . import pk

VERSION = 'one-compartment-absorption-v1'


def capture(compound):
    if compound is None:
        return None
    parameters = pk.profile(compound.name)
    info = pk.model_info(compound.name)
    if parameters is None or info.get('needs_assumptions'):
        return None
    return {
        'model_version': VERSION,
        'compound_name': compound.name,
        'half_life_hours': float(parameters[0]),
        'absorption_half_life_hours': float(parameters[1]),
        'evidence': info,
    }


def resolve(compound, original=None):
    current = capture(compound)
    if original is None:
        return current, 'current', False

    if (
        not isinstance(original, dict)
        or original.get('model_version') != VERSION
    ):
        raise ValueError('Unsupported historical PK model version')

    try:
        half = float(original['half_life_hours'])
        absorption = float(
            original['absorption_half_life_hours']
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            'Invalid historical PK model parameters'
        ) from exc

    if not all(
        isfinite(x) and 0 < x <= 10000
        for x in (half, absorption)
    ):
        raise ValueError(
            'Historical PK model parameters out of range'
        )

    historical = dict(
        original,
        half_life_hours=half,
        absorption_half_life_hours=absorption,
    )

    drift = current is None or any(
        current[key] != historical[key]
        for key in (
            'half_life_hours',
            'absorption_half_life_hours',
        )
    )

    return historical, 'saved', drift
