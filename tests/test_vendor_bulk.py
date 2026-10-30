import io
import csv
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base, VendorPriceSheet, VendorPriceEntry
from app.routers.vendor_prices import bulk_export_csv, parse_bulk_csv, validate_bulk_ids, bulk_save


def test_round_trip_and_missing_ids():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        sheet = VendorPriceSheet(vendor='Vendor A', name='Manual entries')
        db.add(sheet); db.flush()
        entry = VendorPriceEntry(sheet_id=sheet.id, item_name='Compound A', strength='10 mg/vial', content_amount=10, content_unit='mg', package='kit', vial_count=10, total_price_cents=12345, product_url='https://example.org/item')
        db.add(entry); db.commit()
        rows = parse_bulk_csv(bulk_export_csv(db).encode())
        assert rows[0]['_id'] == entry.id
        assert rows[0]['_cents'] == 12345
        assert validate_bulk_ids(db, rows)[entry.id].item_name == 'Compound A'
        rows[0]['_id'] = 99999
        with pytest.raises(ValueError, match='Unknown'):
            validate_bulk_ids(db, rows)


def test_bulk_validation():
    header = 'id,vendor,item_name,content_amount,content_unit,package,vial_count,total_price,product_url\n'
    good = '1,Vendor A,Compound A,10,mg,kit,10,120.50,https://example.org\n'
    assert parse_bulk_csv((header + good).encode())[0]['_cents'] == 12050
    with pytest.raises(ValueError, match='duplicate ID'):
        parse_bulk_csv((header + good + good).encode())
    with pytest.raises(ValueError, match='price'):
        parse_bulk_csv((header + good.replace('120.50', '-2')).encode())
    with pytest.raises(ValueError, match='header'):
        parse_bulk_csv(b'id,vendor\n1,foo\n')


def test_legacy_unknown_content_roundtrip_and_guard():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        sheet = VendorPriceSheet(vendor='Legacy Vendor', name='Old sheet')
        db.add(sheet); db.flush()
        legacy = VendorPriceEntry(sheet_id=sheet.id, item_name='Unknown vial', strength='old label',
                                  content_amount=None, content_unit=None, package='kit',
                                  vial_count=10, total_price_cents=2500)
        known = VendorPriceEntry(sheet_id=sheet.id, item_name='Known vial', strength='10 mg/vial',
                                 content_amount=10, content_unit='mg', package='vial',
                                 vial_count=1, total_price_cents=1000)
        db.add_all([legacy, known]); db.commit()
        rows = parse_bulk_csv(bulk_export_csv(db).encode())
        assert rows[0]['_amount'] is None
        validate_bulk_ids(db, rows)
        rows[0]['_id'] = None
        with pytest.raises(ValueError, match='Blank content'):
            validate_bulk_ids(db, rows)
        rows[0]['_id'] = legacy.id
        rows[1]['_amount'] = None
        rows[1]['content_amount'] = ''
        rows[1]['content_unit'] = ''
        with pytest.raises(ValueError, match='Blank content'):
            validate_bulk_ids(db, rows)

def test_new_offer_requires_content():
    header = ','.join(('id','vendor','item_name','content_amount','content_unit','package','vial_count','total_price','product_url'))
    with pytest.raises(ValueError, match='Content per vial'):
        parse_bulk_csv((header+'\n,Vendor,Item,,,kit,10,12.00,\n').encode())
