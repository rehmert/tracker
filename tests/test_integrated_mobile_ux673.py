"""Release 673 integrated mobile UX: structural and compatibility contracts."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app/templates"
CSS = ROOT / "app/static/css"


def test_673_single_five_destination_mobile_dock_and_existing_quick_sheet():
    html = (TPL / "base.html").read_text(encoding="utf-8")
    dock = html.split('<nav class="tracker-mobile-dock"', 1)[1].split("</nav>", 1)[0]
    assert dock.count("<a ") == 4
    assert dock.count("<button ") == 1
    for url in ('href="/"', 'href="/mobile"', 'href="/quick-entry"',
                'href="/workouts/quick"'):
        assert url in dock
    assert 'id="tracker-mobile-more"' in dock
    assert 'id="tracker-mobile-add528"' in dock
    assert "tracker-mobile-ux673.css?v=673" in html
    assert html.index("tracker-mobile-density600.css") < html.index(
        "tracker-mobile-ux673.css"
    )
    assert '<a href="/doses"' not in dock
    assert '<a href="/vitals"' not in dock
    Environment().parse(html)


def test_673_food_focus_preserves_every_existing_capability():
    html = (TPL / "food.html").read_text(encoding="utf-8")
    fast = html.split('class="food424-actions food-mobile-actions602 ux673-food-primary"', 1)[1]
    fast = fast.split("</nav>", 1)[0]
    assert fast.count("<a ") == 4
    for anchor in ("#food-quick-log", "#food-add", "#food-water", "#food-recorded"):
        assert f'href="{anchor}"' in fast
    assert '<details class="ux673-food-more">' in html
    for target in ("#food-search", "#food-name-search", "#food-templates",
                   "#food-meal-totals", "#food-week", "#food-nutrient-week",
                   "#food-targets", "/food/duplicates"):
        assert f'href="{target}"' in html
    assert html.count('data-food382-section="') == 9
    assert 'tracker-food-ux673.css?v=673' in html
    assert '/food/entry' in html
    assert '/food/quick/' in html
    Environment().parse(html)


def test_673_gym_keeps_recording_and_offline_sync_but_defers_advanced_tools():
    html = (TPL / "workout_quick659.html").read_text(encoding="utf-8")
    assert 'class="ux673-gym-links"' in html
    assert "<summary>More</summary>" in html
    assert "href=\"/workouts/analytics\"" in html
    assert "href=\"/workouts/insights\"" in html
    assert '<details class="ux673-gym-offline"' in html
    assert "<summary>Offline &amp; Draft Tools</summary>" in html
    assert '<button class="primary workout659-main-button" type="submit" id="workout659-save">' in html
    for name in ("draft-save", "draft-restore", "queue-set",
                 "sync-now", "queue-discard", "draft-clear"):
        assert f'id="workout668-{name}"' in html
    assert 'tracker-workout-ux673.css?v=673' in html
    Environment().parse(html)


def test_673_inventory_uses_existing_purchase_mode_and_new_single_row_cards():
    purchase = (TPL / "purchases.html").read_text(encoding="utf-8")
    assert '<table id="purchase-history-table"' in purchase
    assert 'class="ux673-card-table" id="purchase-history-table"' not in purchase
    assert "tracker-purchase-mobile603.js?v=603" in purchase
    for name in ("Date", "Vendor", "Order", "Vials", "Supplies / pills",
                 "Total", "Next step"):
        assert f'data-label="{name}"' in purchase
    for file, key, expected in (
        ("coas.html", "c.id", 8),
        ("supplies.html", "s.id", 7),
    ):
        html = (TPL / file).read_text(encoding="utf-8")
        assert '<table class="ux673-card-table"' in html
        assert html.count('data-label=') >= expected - 1
        assert 'data-ux673-action' in html
        Environment().parse(html)
    assert '<table id="tracker-vials-sortable">' in (
        TPL / "vials.html").read_text(encoding="utf-8")


def test_673_shared_mobile_css_is_scoped_and_preserves_touch_targets():
    css = (CSS / "tracker-mobile-ux673.css").read_text(encoding="utf-8")
    assert "repeat(5, minmax(0, 1fr))" in css
    assert "min-height: 44px" in css
    assert "--ux673-card-pad" in css
    assert 'data-density="comfortable"' in css
    assert 'data-density="compact"' in css
    assert "table.ux673-card-table" in css
    assert "tr[hidden] { display: none !important; }" in css
    assert css.count("{") == css.count("}")
