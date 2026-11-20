"""Release 714: real routine Jinja markup + Chromium computed-box regression.

This is a *source-only* layout witness. It uses synthetic routine items,
never connects to a Tracker server, and does not modify DEV/PROD data.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/workout_routine_detail655.html"
STYLE = ROOT / "app/static/css/tracker-workouts655.css"
STYLE654 = ROOT / "app/static/css/tracker-workouts654.css"
OVERRIDE714 = ROOT / "app/static/css/tracker-workout-routine-alignment714.css"

EXERCISES = [
    "Triceps Press",
    "Seated Leg Curl",
    "Leg Press",
    "Hip Abduction",
    "Hip Adduction",
    "Row",
    "Pulldown",
    "Leg Extension",
    "Standing Calf Raise",
]


def gate714(stage, condition):
    if not condition:
        print("TARGETED_714_" + stage + "=FAILED", flush=True)
    assert condition, stage


def real_routine_markup():
    source = TEMPLATE.read_text(encoding="utf-8")
    gate714("TEMPLATE_SECTION", source.count('<section id="routine-exercises655">') == 1)
    gate714("SHARED_CSS_REF", source.count("/static/css/tracker-workouts655.css?v=655") == 1)
    gate714("NEW_CSS_REF", source.count("/static/css/tracker-workout-routine-alignment714.css?v=714") == 1)
    section = source.split('<section id="routine-exercises655">', 1)[1].split(
        '</section>', 1
    )[0]
    # Render real template fragment, including the original signed-capable
    # POST actions. No hand-written stand-in for card structure.
    try:
        fragment = templates.env.from_string(
            '<section id="routine-exercises655">' + section + '</section>'
        )
    except Exception:
        print("TARGETED_714_TEMPLATE_PARSE=FAILED", flush=True)
        raise
    items = [
        SimpleNamespace(id=700 + i, equipment_id=800 + i)
        for i in range(len(EXERCISES))
    ]
    machine = SimpleNamespace(
        id=999, name="Leg Curl", gym="Merritt Athletic Club - Eldersburg"
    )
    print("RELEASE_714_DIAG_RENDER=STARTED", flush=True)
    try:
        body = fragment.render(
            items=items,
            routine=SimpleNamespace(id=42, name="QA714 Routine"),
            names={item.equipment_id: name for item, name in zip(items, EXERCISES)},
            available=[machine],
            active=None, can_resume=False, maximum=25,
        )
    except Exception:
        print("TARGETED_714_TEMPLATE_RENDER=FAILED", flush=True)
        raise
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>'
        '*{box-sizing:border-box}'
        'body{margin:0;font:16px/1.5 system-ui, sans-serif}'
        'main{padding:8px}'
        'form{margin:0}'
        'label{display:block}'
        'select{padding:.55rem;border:1px solid #aabbd0;border-radius:.5rem}'
        'button{min-height:44px;padding:.5rem .7rem;'
        'border:1px solid #8ca1b8;border-radius:.5rem;background:#fff}'
        + '</style><style>'
        + STYLE654.read_text(encoding="utf-8")
        + '</style><style>'
        + STYLE.read_text(encoding="utf-8")
        + '</style><style>'
        + OVERRIDE714.read_text(encoding="utf-8")
        + '</style></head><body><main class="workout654 workout655">'
        + body + '</main></body></html>'
    )


def test_714_contract_only_changes_layout_not_routine_actions():
    markup = real_routine_markup()
    # The full page includes CSS attribute selectors containing /substitute.
    # Count actual rendered form markup only, never occurrences in CSS text.
    body = markup.split('</style></head><body><main class="workout654 workout655">', 1)[1]
    gate714("ROW_COUNT", body.count('class="workout-routine-row655"') == len(EXERCISES))
    gate714("SELECT_COUNT", body.count('name="equipment_id" required') == len(EXERCISES))
    gate714("BUTTON_COUNT", body.count('type="submit"') >= len(EXERCISES) * 4)
    gate714("UP_COUNT", body.count('name="direction" value="up"') == len(EXERCISES))
    gate714("DOWN_COUNT", body.count('name="direction" value="down"') == len(EXERCISES))
    gate714("SUBSTITUTE_COUNT", body.count('/substitute"') == len(EXERCISES))
    gate714("REMOVE_COUNT", body.count('/remove"') == len(EXERCISES))
    gate714("CSS_GRID_SELECTOR", OVERRIDE714.read_text(encoding="utf-8").count(
        ".workout655 .workout-routine-row655 {"
    ) == 1)
    gate714("CSS_GRID", "display: grid;" in OVERRIDE714.read_text(encoding="utf-8"))
    print("RELEASE_714_CONTRACT=PASSED", flush=True)


@pytest.mark.parametrize("width", [320, 375, 390, 430, 600, 768, 1024, 1280])
def test_714_short_row_title_stays_above_controls_no_overlap(width):
    markup = real_routine_markup()
    print(f"RELEASE_714_DIAG_WIDTH_{width}=STARTED", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 820})
            page.set_content(markup)
            cards = page.locator(".workout-routine-row655")
            assert cards.count() == len(EXERCISES)
            boxes = cards.evaluate_all("""els => els.map(card => {
              const r=card.getBoundingClientRect();
              const title=card.querySelector('.workout-routine-heading655');
              const heading=title.getBoundingClientRect();
              const a=card.querySelector('.workout-routine-actions655');
              const actions=a.getBoundingClientRect();
              const select=a.querySelector('select').getBoundingClientRect();
              const forms=Array.from(a.querySelectorAll('form'));
              const buttons=Array.from(a.querySelectorAll('button'));
              const buttonBoxes=buttons.map(b => b.getBoundingClientRect());
              const text=title.querySelector('strong').textContent.trim();
              const position=title.querySelector('span').getBoundingClientRect();
              return {
                text, display:getComputedStyle(card).display,
                cardX:r.x, cardRight:r.right, cardTop:r.top, cardBottom:r.bottom,
                headingX:heading.x, headingY:heading.y,
                headingBottom:heading.bottom, positionY:position.y,
                actionsX:actions.x, actionsY:actions.y, actionsBottom:actions.bottom,
                selectX:select.x, selectRight:select.right,
                selectWidth:select.width, count:buttons.length,
                buttons:buttonBoxes.map(b => ({
                  x:b.x, right:b.right, y:b.y, bottom:b.bottom, height:b.height
                })),
                actionsRight:actions.right, forms:forms.length
              };
            })""")
            gate714(f"WIDTH_{width}_NAMES", [b["text"] for b in boxes] == EXERCISES)
            gate714(f"WIDTH_{width}_GRID", [b["display"] for b in boxes] == ["grid"] * len(EXERCISES))
            short = next(b for b in boxes if b["text"] == "Row")
            long = next(b for b in boxes if b["text"] == "Hip Adduction")
            # Consistent card-relative starting position regardless of title length.
            gate714(f"WIDTH_{width}_HEADING", abs((short["headingY"] - short["cardTop"]) -
                       (long["headingY"] - long["cardTop"])) < 2)
            for b in boxes:
                gate714(f"WIDTH_{width}_STACK", b["headingBottom"] + 2 <= b["actionsY"])
                gate714(f"WIDTH_{width}_CARD_HEIGHT", b["actionsBottom"] <= b["cardBottom"] + 2)
                gate714(f"WIDTH_{width}_COLUMN", abs(b["headingX"] - b["actionsX"]) < 2)
                gate714(f"WIDTH_{width}_SELECT_WIDTH", b["selectWidth"] >= 100)
                gate714(f"WIDTH_{width}_SELECT_OVERFLOW", b["selectRight"] <= b["cardRight"] + 2)
                gate714(f"WIDTH_{width}_ACTIONS_OVERFLOW", b["actionsRight"] <= b["cardRight"] + 2)
                gate714(f"WIDTH_{width}_FORMS", b["count"] == 4 and b["forms"] == 4)
                gate714(f"WIDTH_{width}_BUTTON_HEIGHT", all(x["height"] >= 44 for x in b["buttons"]))
                gate714(f"WIDTH_{width}_BUTTON_OVERFLOW", all(x["right"] <= b["cardRight"] + 2
                           for x in b["buttons"]))
            gate714(f"WIDTH_{width}_PAGE_OVERFLOW", page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ))
            print(f"RELEASE_714_DIAG_WIDTH_{width}=PASSED", flush=True)
        finally:
            browser.close()
