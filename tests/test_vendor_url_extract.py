import pytest
from app.vendor_url_extract import extract_product, public_url


def test_json_ld_product():
    html='''<html><title>Fallback</title><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Compound X 10 mg 10 vials","offers":{"@type":"Offer","price":"120.00","priceCurrency":"USD"}}</script></html>'''
    result=extract_product(html,'https://example.com/p')
    assert result['name']=='Compound X 10 mg 10 vials'
    assert result['price']=='120.00'
    assert result['content_amount']=='10'
    assert result['package_type']=='kit'


def test_no_guessed_price():
    result=extract_product('<title>Compound X</title><p>Sale 25% off, $30 and $100</p>','https://example.com')
    assert result['price']==''


def test_block_local_ip():
    for url in ['http://127.0.0.1','http://169.254.169.254','http://10.0.0.2','file:///etc/passwd']:
        with pytest.raises(ValueError): public_url(url)
