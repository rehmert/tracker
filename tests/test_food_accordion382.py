"""Release 382: Food Journal accordion source contracts."""

from pathlib import Path
import re

from jinja2 import Environment

TEMPLATE = Path("app/templates/food.html")
SCRIPT = Path("app/static/js/tracker-food382.js")
STYLES = Path("app/static/css/tracker-food382.css")

IDS = (
    "food-search",
    "food-name-search",
    "food-quick-log",
    "food-add",
    "food-templates",
    "food-week",
    "food-meal-totals",
    "food-nutrient-week",
    "food-recorded",
)


def test_food_template_parses():
    Environment().parse(TEMPLATE.read_text())


def test_all_long_sections_are_collapsible():
    source = TEMPLATE.read_text()

    for section_id in IDS:
        assert re.search(
            rf'<details id="{section_id}" '
            rf'class="[^"]*\bfood382-accordion\b',
            source,
        ), section_id

    assert source.count(
        'data-food382-section="'
    ) == len(IDS)


def test_daily_totals_remain_visible():
    source = TEMPLATE.read_text()

    assert '<section class="food-dashboard">' in source
    assert '<h2>Daily Totals</h2>' in source

    # The dashboard is above the first accordion.
    assert source.index('class="food-dashboard"') < source.index(
        'data-food382-section='
    )


def test_food_entry_routes_are_preserved():
    source = TEMPLATE.read_text()

    for route in (
        '/food/entry',
        '/food/quick/',
        '/food/entry/{{ e.id }}/edit',
        '/food/entry/{{ e.id }}/nutrition',
        '/food/template/save',
        '/food/export.csv',
        '/food/weekly.csv',
    ):
        assert route in source


def test_search_and_navigation_autoexpand():
    source = SCRIPT.read_text()

    assert "section.open = true" in source
    assert "food-search" in source
    assert "food-add" in source
    assert "food380-results" in source


def test_accordion_assets_registered():
    source = TEMPLATE.read_text()
    assert "tracker-food382.css?v=382" in source
    assert "tracker-food382.js?v=382" in source
    assert STYLES.exists()
    assert SCRIPT.exists()
