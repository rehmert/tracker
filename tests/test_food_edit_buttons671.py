"""Release 671: all four saved-food edit entry points have matching buttons."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def test_671_all_saved_food_edit_entry_points_use_button_forms():
    template = (ROOT / "app/templates/food.html").read_text(encoding="utf-8")
    assert template.count('<form method="get" action="/food/saved/{{ item.id }}/edit">') == 3
    assert template.count('<form method="get" action="/food/saved/{{ e.product_id }}/edit">') == 1
    assert template.count('<button type="submit">Edit Saved Food</button>') == 4
    assert template.count('class="food375-actions"') >= 4
    assert '<a href="/food/saved/{{ item.id }}/edit' not in template
    assert '<a href="/food/saved/{{ e.product_id }}/edit' not in template
    Environment().parse(template)


def test_671_edit_buttons_have_mobile_touch_targets():
    stylesheet = (ROOT / "app/static/css/tracker-food375.css").read_text(encoding="utf-8")
    assert ".food375-actions button { min-height: 44px; }" in stylesheet
    assert ".food375-actions form { flex: 1; }" in stylesheet
    assert ".food375-actions button { width: 100%; }" in stylesheet
