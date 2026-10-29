from decimal import Decimal
from unittest.mock import Mock, patch
from app.models import VendorShippingRule
from app.routers.vendor_prices import shipping_for_order, shipping_details, save_shipping, delete_shipping


def test_shipping_threshold_inclusive():
    rule = VendorShippingRule(vendor='Vendor', vendor_key='vendor', flat_shipping_cents=1500, free_shipping_threshold_cents=20000)
    assert shipping_for_order(rule, 19999) == 1500
    assert shipping_for_order(rule, 20000) == 0
    assert shipping_for_order(rule, 25000) == 0


def test_landed_per_vial():
    entry = Mock(id=1, total_price_cents=10000, vial_count=5)
    entry.sheet.vendor = '  VENDOR  '
    rule = VendorShippingRule(vendor='Vendor', vendor_key='vendor', flat_shipping_cents=1200, free_shipping_threshold_cents=20000)
    result = shipping_details(entry, {'vendor': rule})
    assert result['shipping_cents'] == 1200
    assert result['landed_cents'] == 11200
    assert result['landed_per_vial_cents'] == 2240
    assert shipping_details(entry, {})['configured'] is False


def test_save_shipping_new_vendor():
    db = Mock()
    db.scalars.return_value.first.return_value = None
    with patch('app.routers.vendor_prices.services.flash_redirect', return_value='ok'):
        assert save_shipping(Mock(), '  Vendor A ', '12.50', '200', db) == 'ok'
    rule = db.add.call_args.args[0]
    assert rule.vendor_key == 'vendor a'
    assert rule.flat_shipping_cents == 1250
    assert rule.free_shipping_threshold_cents == 20000
    db.commit.assert_called_once()


def test_delete_shipping():
    db = Mock()
    db.get.return_value = VendorShippingRule(vendor='A', vendor_key='a', flat_shipping_cents=0, free_shipping_threshold_cents=100)
    with patch('app.routers.vendor_prices.services.flash_redirect', return_value='ok'):
        assert delete_shipping(3, db) == 'ok'
    db.delete.assert_called_once()
    db.commit.assert_called_once()
