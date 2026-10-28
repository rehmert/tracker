from app.vendor_prices import parse_lines, count_from_text, normalize_item
from app.routers.vendor_prices import parse_review, rows_text

def test_csv_sheet_and_unit_normalization():
    rows = parse_lines('Item,Strength,Quantity,Price\nCompound A,10 mg,10,$120\nCompound B,5 mg,5,$45')
    assert len(rows) == 2
    assert rows[0][3] == 10
    assert rows[0][4] / rows[0][3] == 12
    assert parse_review(rows_text(rows)) == rows

def test_simple_ocr_and_package_counts():
    assert count_from_text('half-kit') == 5
    assert count_from_text('kit') == 10
    assert parse_lines('Compound A 10mg kit $120')[0][3] == 10
    assert normalize_item('Compound-A') == normalize_item('compound a')

def test_review_rejects_bad_price():
    import pytest
    with pytest.raises(ValueError):
        parse_review('Item\tStrength\tPackage\tVials\tTotal USD\nX\t10mg\tkit\t10\t-5')
