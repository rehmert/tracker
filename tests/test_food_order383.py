"""Release 383: mobile Food Journal ordering contracts."""

import re
from pathlib import Path

from jinja2 import Environment

SOURCE = Path("app/templates/food.html").read_text()

ORDER = [
    "food-recorded",
    "food-quick-log",
    "food-search",
    "food-name-search",
    "food-add",
    "food-templates",
    "food-meal-totals",
    "food-week",
    "food-nutrient-week",
]


def test_template_syntax():
    Environment().parse(SOURCE)


def test_daily_totals_first():
    assert SOURCE.index('class="food-dashboard"') < SOURCE.index('id="food-recorded"') < SOURCE.index('id="food-add-workspace792"')


def test_accordion_order():
    actual = re.findall(
        r'<details id="(food-[^"]+)" '
        r'class="[^"]*food382-accordion',
        SOURCE,
    )

    assert actual == ORDER


def test_navigation_matches_section_order():
    destinations = re.findall(r'href="#(food-[^"]+)"', SOURCE)
    assert set(ORDER).issubset(set(destinations))
    for name in ("food-add-workspace792", "food-meals792", "food-analysis792"):
        assert f'id="{name}"' in SOURCE


def test_all_sections_still_collapsible():
    assert SOURCE.count(
        'data-food382-section="'
    ) == 9


def test_existing_food_workflows_preserved():
    for endpoint in (
        "/food/entry",
        "/food/quick/",
        "/food/entry/{{ e.id }}/edit",
        "/food/entry/{{ e.id }}/nutrition",
        "/food/template/save",
        "/food/weekly.csv",
        "/food/export.csv",
    ):
        assert endpoint in SOURCE
