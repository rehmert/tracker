import pytest
from app.routers.labs import _parse_csv_data


def test_csv_import_valid_and_bom():
    rows = _parse_csv_data('analyte,value,unit,ref_low,ref_high,note\nTSH,1.25,mIU/L,0.4,4.5,ok\nIGF-1,180,ng/mL,,,\n'.encode('utf-8-sig'))
    assert len(rows) == 2
    assert rows[0].note == 'ok'
    assert rows[0].ref_low == 0.4
    assert rows[1].ref_high is None


def test_csv_import_header_aliases():
    rows = _parse_csv_data(b'Test Name,Result,Units,Range Low,Range High\nTSH,2,mIU/L,0,4\n')
    assert rows[0].analyte == 'TSH'

@pytest.mark.parametrize('data', [
    b'analyte,value,unit\nTSH,abc,mIU/L\n',
    b'analyte,value,unit\nTSH,nan,mIU/L\n',
    b'analyte,value,unit\nTSH,1,mIU/L,extra\n',
    b'analyte,value,unit,ref_low,ref_high\nTSH,1,mIU/L,0,\n',
    b'foo,bar\na,b\n',
    b'analyte,value,unit\n',
    b'analyte,value,unit\nTSH,1,mIU/L\nIGF-1,no,ng/mL\n',
])
def test_invalid_csv_rejected(data):
    with pytest.raises(ValueError):
        _parse_csv_data(data)
