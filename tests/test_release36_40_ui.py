"""Non-destructive smoke checks for the consolidated UX release."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_shared_assets_are_loaded():
    base = (ROOT / 'app/templates/base.html').read_text()
    assert '/static/release36_40.css?v=1' in base
    assert '/static/release36_40.js?v=1' in base
    assert (ROOT / 'app/static/release36_40.css').exists()
    assert (ROOT / 'app/static/release36_40.js').exists()

def test_inventory_issues_has_one_canonical_inventory_navigation_entry():
    # Release 793 consolidated the old Inventory tools group.
    from app.navigation import NAVIGATION, current_navigation
    groups = [(key, title, label, primary)
              for key, title, links in NAVIGATION
              for href, label, primary in links if href == "/inventory-health"]
    assert groups == [("Inventory", "Inventory", "Inventory issues", True)]
    assert current_navigation("/inventory-health") == "/inventory-health"
    base = (ROOT / 'app/templates/base.html').read_text()
    assert "{% for section, group_label, links in tracker_navigation %}" in base

def test_inventory_health_explains_non_mutating_diagnostics():
    html = (ROOT / 'app/templates/inventory_health.html').read_text()
    assert 'No stock is changed' in html
    assert html.count('No stock is changed') == 1

def test_enhanced_tables_are_explicitly_opted_in():
    for name in ('inventory_health.html', 'supplies.html'):
        assert 'data-enhanced-table' in (ROOT / 'app/templates' / name).read_text()
    assert 'data-enhanced-table' not in (ROOT / 'app/templates/vials.html').read_text()


def test_purchases_use_dedicated_review_instead_of_generic_table_tools():
    purchases = (ROOT / 'app/templates/purchases.html').read_text()
    assert 'data-enhanced-table' not in purchases
    assert 'data-purchase-history' in purchases
    assert 'data-purchase-review-toolbar' in purchases
    assert 'tracker-purchase-history-review.js?v=603' in purchases
    assert 'tracker-purchase-history-review.css?v=20261103' in purchases
    # The Purchase creation form must remain untouched by the review controls.
    assert '<form method="post" action="/purchases"' in purchases
