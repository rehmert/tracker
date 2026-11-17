"""Release 672: no redundant saved-food confirmation and consistent actions."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1] / "app/templates"


def test_672_saved_food_update_requires_only_save():
    source = (ROOT.parent / "routers/food.py").read_text(encoding="utf-8")
    markup = (ROOT / "food_saved_edit669.html").read_text(encoding="utf-8")
    assert 'name="confirm_history"' not in markup
    assert 'form.get("confirm_history"' not in source
    assert "if used and confirm" not in source
    assert "Existing meal history:" in markup
    assert '<button type="submit" class="primary">Save Food Changes</button>' in markup
    assert '<a class="btn" href="/food?day={{ day }}#food-search">Cancel</a>' in markup


def test_672_cancel_controls_consistent_on_editor_pages():
    expected = {
        "compound_edit.html": '<a class="btn" href="/compounds">Cancel</a>',
        "page_edit.html": '<a class="btn" href="{{ \'/pages/\' ~ p.id if p else \'/pages\' }}">Cancel</a>',
        "lab_form.html": '<a class="btn" href="/labs">Cancel</a>',
        "workout_backfill658.html": '<a class="btn" href="/workouts">Cancel</a>',
        "vendor_prices.html": '<a class="btn" href="/vendor-prices">Cancel</a>',
        "food_saved_edit669.html": '<a class="btn" href="/food?day={{ day }}#food-search">Cancel</a>',
    }
    for file, marker in expected.items():
        html = (ROOT / file).read_text(encoding="utf-8")
        assert marker in html, file
        Environment().parse(html)


def test_672_compound_and_purchase_actions_are_real_buttons():
    compounds = (ROOT / "compounds.html").read_text(encoding="utf-8")
    assert '<form style="display:inline" method="get" action="/compounds/{{ c.id }}/edit"><button type="submit">Edit</button></form>' in compounds
    assert '<a href="/compounds/{{ c.id }}/edit">Edit</a>' not in compounds
    assert '<button type="submit" style="color:var(--brick)">Delete</button>' in compounds

    purchases = (ROOT / "purchase_detail.html").read_text(encoding="utf-8")
    assert '<form method="get" action="/vials/{{ v.id }}"><button type="submit">Edit</button></form>' in purchases
    assert '<a href="/vials/{{ v.id }}">Edit</a>' not in purchases
    assert '<button type="submit" style="color:var(--brick)">Delete</button>' in purchases
    Environment().parse(compounds)
    Environment().parse(purchases)


def test_672_existing_button_visual_system():
    css = (ROOT.parent / "static/app.css").read_text(encoding="utf-8")
    assert ".btn { display: inline-block;" in css
    assert "button { padding:" in css


def test_672_vendor_and_vitals_edit_controls_are_buttons():
    vendor = (ROOT / "vendor_prices.html").read_text(encoding="utf-8")
    assert '<form method="get" action="/vendor-prices/entries/{{ e.id }}/edit#edit-offer" style="display:inline"><button type="submit">Edit</button></form>' in vendor
    # An independent Download anchor is intentionally button-styled; only
    # the Vendor Price Edit control must be an actual form button.
    assert '<a href="/vendor-prices/entries/{{ e.id }}/edit#edit-offer"' not in vendor
    vitals = (ROOT / "vitals.html").read_text(encoding="utf-8")
    assert '<form method="get" action="/vitals/{{ r.id }}/edit" style="display:inline">' in vitals
    assert '<input type="hidden" name="days" value="{{ days }}">' in vitals
    assert '<input type="hidden" name="events" value="{{ 1 if events_on else 0 }}">' in vitals
    assert 'hx-delete="/vitals/{{ r.id }}"' in vitals
    assert 'hx-confirm="Delete this reading?"' in vitals
    assert '<a class="link" href="/vitals/{{ r.id }}/edit' not in vitals
    Environment().parse(vendor)
    Environment().parse(vitals)
