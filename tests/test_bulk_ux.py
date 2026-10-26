from pathlib import Path
from app.models import SupplyProduct


def test_catalog_schema():
    assert SupplyProduct.__tablename__ == 'supply_products'
    assert 'units_per_pack' in SupplyProduct.__table__.columns


def test_purchase_ui_fields():
    text = (Path(__file__).parents[1] / 'app/templates/purchase_detail.html').read_text()
    assert 'Total line price' in text
    assert 'data-product-picker' in text
    assert 'data-bulk-ux' in text


def test_price_preview_and_mode_switch():
    text = (Path(__file__).parents[1] / 'app/static/bulk_purchase_ux.js').read_text()
    assert 'unitFields.hidden = bulk' in text
    assert 'count * per' in text
