"""Small, accessible SVG sparklines from recorded numeric measurements only."""
from datetime import datetime
from html import escape
from math import isfinite


def sparkline(points: list[tuple[datetime, float]], label: str, *, days: int = 30, now: datetime | None = None) -> str:
    """Return an SVG trend line, or an empty string if fewer than two readings."""
    from datetime import timedelta
    now = now or datetime.now()
    samples = sorted((t, float(v)) for t, v in points
                     if t >= now - timedelta(days=days) and v is not None and isfinite(float(v)))
    if len(samples) < 2:
        return ""
    samples = samples[-90:]
    lo, hi = min(v for _, v in samples), max(v for _, v in samples)
    spread = hi - lo
    start, end = samples[0][0], samples[-1][0]
    span = (end - start).total_seconds()
    coords = []
    for index, (t, value) in enumerate(samples):
        x = 6 + 148 * ((t - start).total_seconds() / span if span else index / max(len(samples) - 1, 1))
        y = 37 - 29 * ((value - lo) / spread if spread else .5)
        coords.append(f"{x:.1f},{y:.1f}")
    return (f'<svg class="metric-sparkline" viewBox="0 0 160 46" role="img" '
            f'aria-label="{escape(label, quote=True)} trend over the last {days} days">'
            f'<polyline points="{" ".join(coords)}" fill="none" stroke="currentColor" '
            f'stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>'
            f'</svg>')
