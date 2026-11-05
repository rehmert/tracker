"""Release 383: mobile Food Journal ordering contracts."""

import re
from pathlib import Path

from jinja2 import Environment

SOURCE = Path("app/templates/food.html").read_text()

ORDER = [
    "food-quick-log",
    "food-search",
    "food-name-search",
    "food-add",
    "food-recorded",
    "food-templates",
    "food-meal-totals",
    "food-week",
    "food-nutrient-week",
]


def test_template_syntax():
    Environment().parse(SOURCE)


def test_daily_totals_first():
    dashboard = SOURCE.index(
        'class="food-dashboard"'
    )
    navigation = SOURCE.index(
        'class="food376-nav"'
    )
    first_section = SOURCE.index(
        'id="food-quick-log"'
    )

    assert dashboard < navigation < first_section


def test_accordion_order():
    actual = re.findall(
        r'<details id="(food-[^"]+)" '
        r'class="[^"]*food382-accordion',
        SOURCE,
    )

    assert actual == ORDER


def test_navigation_matches_section_order():
    match = re.search(
        r'<nav class="food376-nav"[^>]*>'
        r'(.*?)</nav>',
        SOURCE,
        re.S,
    )
    assert match

    actual = re.findall(
        r'href="#(food-[^"]+)"',
        match.group(1),
    )

    assert actual == ORDER


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
