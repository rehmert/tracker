from datetime import date, datetime, timedelta

import pytest

from app import charts, labs


def test_alias_and_unit_normalising():
    assert labs.analyte_key("Total Testosterone") == "testosterone"
    assert labs.analyte_key("  HGB ") == "hemoglobin"
    assert labs.analyte_key("Ferritin") == "ferritin"
    assert labs.norm_unit(" µmol / L ") == "umol/l"


def test_conversions_both_directions():
    assert labs.convert("Total testosterone", 600, "ng/dL", "nmol/L") == pytest.approx(20.802, rel=1e-3)
    assert labs.convert("testosterone", 20.8, "nmol/L", "ng/dL") == pytest.approx(600, rel=1e-3)
    assert labs.convert("Glucose", 5.0, "mmol/L", "mg/dL") == pytest.approx(90.08, rel=1e-3)
    assert labs.convert("Creatinine", 1.0, "mg/dL", "µmol/L") == pytest.approx(88.4)
    assert labs.convert("Ferritin", 50, "ng/mL", "ug/L") is None      # no table entry: don't guess
    assert labs.convert("Ferritin", 50, "ng/mL", "ng/ml") == 50       # same unit needs none


def test_build_series_uses_newest_unit_and_counts_skips():
    pts = [labs.Point(date(2025, 1, 1), 500, "ng/dL", 264, 916),
           labs.Point(date(2025, 6, 1), 18.0, "nmol/L", 9.2, 31.8),
           labs.Point(date(2025, 7, 1), 5, "weird", None, None)]
    r = labs.build_series("Testosterone", pts)
    assert r.unit == "weird" and r.skipped == 2 and len(r.points) == 1
    r = labs.build_series("Testosterone", pts[:2])
    assert r.unit == "nmol/L" and r.skipped == 0
    assert r.points[0][1] == pytest.approx(17.335, rel=1e-3)
    assert r.band == (9.2, 31.8)
    assert labs.build_series("x", []).points == []


def test_range_status():
    assert labs.range_status(5, 10, 20) == "below"
    assert labs.range_status(15, 10, 20) == "within"
    assert labs.range_status(25, 10, 20) == "above"
    assert labs.range_status(5, None, 20) is None


def _series():
    t = datetime(2026, 10, 1)
    return [charts.Series("Weight", [(t, 80.0), (t + timedelta(days=10), 79.0)])]


def test_chart_with_events_band_and_lanes():
    t = datetime(2026, 10, 1)
    ev = [charts.Event(t + timedelta(days=2), "dose", "Compound A: 250 mcg", "Compound A"),
          charts.Event(t + timedelta(days=4), "dose", "Compound B: 1 mg", "Compound B"),
          charts.Event(t + timedelta(days=4), "dose", "Compound A: 250 mcg", "Compound A"),
          charts.Event(t + timedelta(days=3), "marker", "Compound A 10 mg", mark="R"),
          charts.Event(t - timedelta(days=30), "marker", "outside range", mark="P")]
    svg = charts.line_chart(_series(), events=ev, band=(78.0, 82.0), band_label="Printed range",
                            x_range=(t, t + timedelta(days=10)))
    assert svg.count('class="tick l0"') == 2 and svg.count('class="tick l1"') == 1
    assert 'class="evline"' in svg and svg.count("evbadge") == 1       # out-of-range marker dropped
    assert 'class="band"' in svg and "Reconstituted" in svg
    assert "Compound A doses" in svg and "(lane 1)" in svg


def test_chart_event_labels_are_escaped():
    t = datetime(2026, 10, 1)
    ev = [charts.Event(t, "dose", "<img src=x onerror=1>", "<b>X</b>"),
          charts.Event(t, "marker", "<script>", mark="P")]
    svg = charts.line_chart(_series(), events=ev)
    assert "<img" not in svg and "<script" not in svg and "<b>X</b>" not in svg and "&lt;b&gt;X" in svg


def test_chart_axis_precision_for_small_values():
    t = datetime(2026, 10, 1)
    svg = charts.line_chart([charts.Series("x", [(t, 0.8), (t + timedelta(days=1), 1.1)], fmt="{:.2f}")])
    assert ">0.7" in svg or ">0.6" in svg or ">0.8" in svg               # not rounded to whole numbers
