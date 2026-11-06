"""Release 424 mobile journal regression tests."""

import re
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'app/templates/food.html').read_text()

MACROS = ('energy', 'proteins', 'carbohydrates', 'fat')
NUTRIENTS = {
    key: (key.title(), 'g')
    for key in MACROS
}


def macro_view(food_count, totals, targets, coverage):
    start = TEMPLATE.index(
        '  <div class="food423-macros"'
    )
    end = TEMPLATE.index(
        '  <details><summary>All Nutrients',
        start
    )

    source = TEMPLATE[start:end]

    return Environment(autoescape=True).from_string(
        source
    ).render(
        food_count=food_count,
        totals={
            key: totals.get(key, 0)
            for key in MACROS
        },
        targets=targets,
        coverage={
            key: coverage.get(key, 0)
            for key in MACROS
        },
        nutrients=NUTRIENTS,
    )


def test_unlogged_day_has_no_false_remaining():
    output = macro_view(
        0,
        {},
        {'energy': 2000, 'proteins': 160},
        {},
    )

    assert output.count('Not logged') == 4
    assert 'No food has been logged' in output
    assert 'role="progressbar"' not in output

    # Jinja round(1) may render 2000 as 2000.0.
    assert re.search(
        r'<strong>\s*2000(?:\.0)?\s*</strong>',
        output,
    )


def test_partial_nutrition_remains_unknown():
    output = macro_view(
        2,
        {'energy': 150},
        {'energy': 200},
        {'energy': 1},
    )

    assert 'Unknown' in output
    assert 'Partial data: 1 of 2' in output
    assert 'role="progressbar"' not in output

    assert (
        'Comparison unavailable: incomplete food data'
        in output
    )


def test_complete_data_shows_remaining_and_overage():
    output = macro_view(
        1,
        {'energy': 250, 'proteins': 20},
        {'energy': 200, 'proteins': 30},
        {'energy': 1, 'proteins': 1},
    )

    assert re.search(
        r'50(?:\.0)?\s+over',
        output,
    )

    assert 'Remaining</small>' in output
    assert output.count('role="progressbar"') == 2


def test_original_nine_accordion_contract():
    original = [
        'food-quick-log',
        'food-search',
        'food-name-search',
        'food-add',
        'food-recorded',
        'food-templates',
        'food-meal-totals',
        'food-week',
        'food-nutrient-week',
    ]

    actual = re.findall(
        r'<details id="(food-[^"]+)" '
        r'class="[^"]*food382-accordion',
        TEMPLATE,
    )

    assert actual == original
    assert TEMPLATE.count('data-food382-section="') == 9


def test_target_editor_is_independent():
    assert (
        '<details id="food-targets" '
        'class="food424-targets">'
    ) in TEMPLATE

    assert TEMPLATE.count('id="food-targets"') == 1
    assert TEMPLATE.count('action="/food/targets"') == 1

    assert (
        TEMPLATE.index('id="food-targets"')
        < TEMPLATE.index('id="food-quick-log"')
    )


def test_mobile_shortcuts_and_assets():
    assert 'href="#food-targets"' in TEMPLATE
    assert 'href="#food-quick-log"' in TEMPLATE
    assert 'href="#food-add"' in TEMPLATE
    assert 'href="#food-search"' in TEMPLATE

    assert 'tracker-food424.css?v=424' in TEMPLATE
    assert 'tracker-food424.js?v=424' in TEMPLATE

    script = (
        ROOT / 'app/static/js/tracker-food424.js'
    ).read_text()

    assert "target.open = true" in script
    assert "location.hash === '#food-targets'" in script


def test_all_nutrition_targets_posted_together():
    assert (
        "key not in ('energy','proteins','carbohydrates','fat')"
        in TEMPLATE
    )

    food = (
        ROOT / 'app/routers/food.py'
    ).read_text()

    assert '"/food/targets"' in food
    assert 'for key in NUTRIENTS:' in food
    assert 'DELETE FROM tracker_food_targets' in food
