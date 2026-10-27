from types import SimpleNamespace
from app.routers.labs import _sort_report_rows


def test_sort_report_rows_numeric_and_text():
    rows = [
        {'res': SimpleNamespace(id=1, analyte='Zinc', value=100, unit='mcg/dL', ref_low=60, ref_high=120, note='z'), 'status': 'within'},
        {'res': SimpleNamespace(id=2, analyte='Albumin', value=4.1, unit='g/dL', ref_low=3.5, ref_high=5.0, note='a'), 'status': 'within'},
    ]
    assert [r['res'].id for r in _sort_report_rows(rows, 'analyte', 'asc')] == [2, 1]
    assert [r['res'].id for r in _sort_report_rows(rows, 'value', 'desc')] == [1, 2]
    assert [r['res'].id for r in _sort_report_rows(rows, 'note', 'asc')] == [2, 1]
    assert [r['res'].id for r in _sort_report_rows(rows, 'invalid', 'invalid')] == [2, 1]
