"""Release 670: Edit Saved Food belongs in the recorded-meal button group."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def test_670_recorded_food_actions_are_four_consistent_buttons():
    html = (ROOT / "app/templates/food.html").read_text(encoding="utf-8")
    # Other Food Journal sections now use the same action class; scope this
    # historical assertion to Recorded Meals rather than the first match.
    recorded = html.split('<details id="food-recorded"', 1)[1]
    recorded = recorded.split('<details id="food-templates"', 1)[0]
    section = recorded.split('<div class="food375-actions">', 1)[1].split("</div>", 1)[0]
    assert section.count("<form ") == 4
    for label in ("Repeat", "Edit Saved Food", "Delete"):
        assert label in section
    assert '<form method="get" action="/food/saved/{{ e.product_id }}/edit">' in section
    assert '<input type="hidden" name="day" value="{{ day }}">' in section
    assert '<button type="submit">Edit Saved Food</button>' in section
    assert "<a " not in section
    Environment().parse(html)


def test_670_existing_mobile_action_layout_applies_to_edit():
    css = (ROOT / "app/static/css/tracker-food375.css").read_text(encoding="utf-8")
    assert ".food375-actions form { flex: 1; }" in css
    assert ".food375-actions button { width: 100%; }" in css
    assert ".food375-actions button { min-height: 44px; }" in css
