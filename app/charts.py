"""Tiny dependency-free SVG line charts, rendered on the server. Pure Python.

A chart can carry:
  * data series (lines with dots),
  * dose events    -> small ticks in one lane per compound under the plot,
  * marker events  -> dashed vertical lines with a letter badge (purchase,
                      reconstitution, first/last use of a vial, lab draw),
  * a shaded reference band (e.g. the range printed on a lab report).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape

MARKS = {"P": "Purchase", "R": "Reconstituted", "S": "First logged use of a vial",
         "F": "Last logged use of a finished or discarded vial", "L": "Lab draw"}
MAX_LANES = 6
MAX_MARKERS = 60


@dataclass
class Series:
    name: str
    points: list[tuple[datetime, float]]
    css: str = "s1"                      # s1 / s2 stroke classes in app.css
    fmt: str = "{:.1f}"


@dataclass
class Event:
    at: datetime
    kind: str                            # "dose" or "marker"
    label: str
    group: str = ""                      # dose events: compound name (one lane each)
    mark: str = ""                       # marker events: one of MARKS


def _axis(v: float, span: float) -> str:
    if span >= 20:
        return f"{v:.0f}"
    if span >= 2:
        return f"{v:.1f}"
    return f"{v:.2f}"


def line_chart(series: list[Series], width: int = 640, plot_h: int = 150, unit: str = "",
               x_range: tuple[datetime, datetime] | None = None,
               events: list[Event] | None = None,
               band: tuple[float, float] | None = None, band_label: str = "") -> str:
    series = [s for s in series if s.points]
    label = ", ".join(s.name for s in series) or "chart"
    if not series:
        return '<p class="empty">No readings in this range yet.</p>'

    # ---- time and value domains
    all_t = [t for s in series for t, _ in s.points]
    t0, t1 = x_range or (min(all_t), max(all_t))
    span = (t1 - t0).total_seconds()
    all_v = [v for s in series for _, v in s.points]
    if band:
        all_v += list(band)
    vmin, vmax = min(all_v), max(all_v)
    pad = (vmax - vmin) * 0.12 or max(abs(vmax) * 0.05, 1.0)
    vmin, vmax = vmin - pad, vmax + pad

    # ---- events
    events = events or []
    doses = [e for e in events if e.kind == "dose" and t0 <= e.at <= t1]
    markers = sorted((e for e in events if e.kind == "marker" and t0 <= e.at <= t1),
                     key=lambda e: e.at)[:MAX_MARKERS]
    counts: dict[str, int] = {}
    for e in doses:
        counts[e.group] = counts.get(e.group, 0) + 1
    groups = sorted(counts, key=lambda g: (-counts[g], g))
    lanes = groups[:MAX_LANES]
    hidden = len(groups) - len(lanes)
    lane_h = 9

    left, right, top = 46, 14, 16
    bottom = 24 + ((6 + lane_h * len(lanes)) if lanes else 0)
    height = top + plot_h + bottom
    pw = width - left - right

    def x(t: datetime) -> float:
        return left + pw * (((t - t0).total_seconds() / span) if span > 0 else 0.5)

    def y(v: float) -> float:
        return top + plot_h * (1 - (v - vmin) / (vmax - vmin))

    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Line chart of {escape(label)}" preserveAspectRatio="xMidYMid meet">']
    if band:
        yb_hi, yb_lo = y(band[1]), y(band[0])
        out.append(f'<rect class="band" x="{left}" y="{yb_hi:.1f}" width="{pw}" '
                   f'height="{max(yb_lo - yb_hi, 1):.1f}"><title>{escape(band_label or "Reference range")}</title></rect>')
    for frac in (0, 0.5, 1):
        v = vmin + (vmax - vmin) * frac
        yy = y(v)
        out.append(f'<line class="gl" x1="{left}" x2="{width - right}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        out.append(f'<text class="axis" x="{left - 6}" y="{yy + 4:.1f}" text-anchor="end">{_axis(v, vmax - vmin)}</text>')
    base_y = top + plot_h
    out.append(f'<text class="axis" x="{left}" y="{base_y + 15}" text-anchor="start">{t0:%b %d, %Y}</text>')
    out.append(f'<text class="axis" x="{width - right}" y="{base_y + 15}" text-anchor="end">{t1:%b %d, %Y}</text>')

    for e in markers:                                   # dashed vertical lines under the data
        ex = x(e.at)
        out.append(f'<line class="evline" x1="{ex:.1f}" x2="{ex:.1f}" y1="{top}" y2="{base_y}"/>')

    for s in series:
        pts = sorted(s.points)
        if len(pts) > 1:
            path = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts)
            out.append(f'<polyline class="line {s.css}" points="{path}"/>')
        for t, v in pts:
            tip = escape(f"{s.name}: {s.fmt.format(v)}{unit} on {t:%Y-%m-%d %H:%M}")
            out.append(f'<circle class="dot {s.css}" cx="{x(t):.1f}" cy="{y(v):.1f}" r="3.2"><title>{tip}</title></circle>')

    for e in markers:                                   # letter badges on top
        ex = x(e.at)
        tip = escape(f"{MARKS.get(e.mark, 'Event')}: {e.label} ({e.at:%Y-%m-%d})")
        out.append(f'<g class="evbadge"><title>{tip}</title><circle cx="{ex:.1f}" cy="{top - 7}" r="7"/>'
                   f'<text x="{ex:.1f}" y="{top - 3.5}" text-anchor="middle">{escape(e.mark or "•")}</text></g>')

    lane_index = {g: i for i, g in enumerate(lanes)}
    for e in doses:
        i = lane_index.get(e.group)
        if i is None:
            continue
        ex = x(e.at)
        y0 = base_y + 22 + i * lane_h
        out.append(f'<line class="tick l{i}" x1="{ex:.1f}" x2="{ex:.1f}" y1="{y0}" y2="{y0 + lane_h - 2}">'
                   f'<title>{escape(e.label)} ({e.at:%Y-%m-%d %H:%M})</title></line>')
    out.append("</svg>")

    legend: list[str] = []
    if len(series) > 1:
        legend += [f'<span class="key {s.css}">{escape(s.name)}</span>' for s in series]
    if band:
        legend.append(f'<span class="key band">{escape(band_label or "Reference range")}</span>')
    for mk in dict.fromkeys(e.mark for e in markers if e.mark in MARKS):
        legend.append(f'<span class="mk"><b>{mk}</b> {escape(MARKS[mk])}</span>')
    for i, g in enumerate(lanes):
        legend.append(f'<span class="lane l{i}">{escape(g)} doses <small>(lane {i + 1})</small></span>')
    if hidden > 0:
        legend.append(f'<small>{hidden} more compound(s) not drawn</small>')
    if legend:
        out.append('<p class="legend">' + " ".join(legend) + "</p>")
    return "".join(out)
