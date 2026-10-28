import pytest
from app.routers.vendor_prices import parse_vendor_items_csv, csv_review_text, CSV_COLUMNS, validate_vendor_csv_row

def test_csv_multi_vendor_and_optional_url():
    data=b'vendor,item_name,content_amount,content_unit,package_type,package_price,product_url\nA,Compound X,10,mg,kit,120,https://example.com/x\nB,Compound Y,500,IU,vial,25,\n'
    rows=parse_vendor_items_csv(data)
    assert len(rows)==2 and rows[1]['vendor']=='B'
    assert rows[0]['product_url']=='https://example.com/x'
    assert csv_review_text(rows).splitlines()[0]=='\t'.join(CSV_COLUMNS)

def test_csv_aliases_and_default_unit():
    rows=parse_vendor_items_csv(b'supplier,compound,strength,package,price\nA,X,10,half-kit,100\n')
    assert rows[0]['content_unit']=='mg'

def test_csv_rejects_bad_url():
    with pytest.raises(ValueError):
        parse_vendor_items_csv(b'vendor,item_name,content_amount,package_type,package_price,product_url\nA,X,10,kit,100,javascript:alert(1)\n')

def test_csv_rejects_missing_columns():
    with pytest.raises(ValueError):
        parse_vendor_items_csv(b'vendor,item_name\nA,X\n')
