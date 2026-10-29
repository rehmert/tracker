from decimal import Decimal
import pytest
from app.vendor_content import parse_legacy_content, validate_content, label

@pytest.mark.parametrize('text,expected', [('15 mg/vial',(Decimal('15'),'mg')),('12 IU',(Decimal('12'),'IU')),('15mg',(Decimal('15'),'mg')),('30 mg (per vial)',(Decimal('30'),'mg'))])
def test_legacy(text, expected):
    assert parse_legacy_content(text) == expected

@pytest.mark.parametrize('text', ['30 mg x 10','unknown','', '20 mg + 10 mg', '0 mg'])
def test_ambiguous(text):
    assert parse_legacy_content(text) == (None,None)

def test_content_validation():
    assert validate_content('15.5','mg') == (Decimal('15.5'),'mg')
    assert label(15.5,'mg') == '15.5 mg/vial'
    with pytest.raises(ValueError):validate_content('NaN','mg')
    with pytest.raises(ValueError):validate_content('15','ml')
