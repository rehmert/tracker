"""Non-destructive smoke checks for the consolidated UX release."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_shared_assets_are_loaded():
    base = (ROOT / 'app/templates/base.html').read_text()
    assert '/static/release36_40.css?v=1' in base
    assert '/static/release36_40.js?v=1' in base
    assert (ROOT / 'app/static/release36_40.css').exists()
    assert (ROOT / 'app/static/release36_40.js').exists()

def test_inventory_tools_are_separate_navigation_group():
    base = (ROOT / 'app/templates/base.html').read_text()
    assert "('Inventory tools'," in base
    assert base.count("('/inventory-health','Inventory health')") == 1

def test_inventory_health_explains_non_mutating_diagnostics():
    html = (ROOT / 'app/templates/inventory_health.html').read_text()
    assert 'No stock is changed' in html
    assert html.count('No stock is changed') == 1

def test_enhanced_tables_are_explicitly_opted_in():
    for name in ('purchases.html', 'inventory_health.html', 'supplies.html'):
        assert 'data-enhanced-table' in (ROOT / 'app/templates' / name).read_text()
    assert 'data-enhanced-table' not in (ROOT / 'app/templates/vials.html').read_text()
