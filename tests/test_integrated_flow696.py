"""Release 696: one coordinated everyday + inventory UI release.

No schema, server route, authentication, CSRF or write-flow changes.
"""
from pathlib import Path
import re

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app/templates"
CSS = ROOT / "app/static/css/tracker-integrated-flow696.css"
JS = ROOT / "app/static/js/tracker-coa-find696.js"
PAGES = {
    "/workouts": "workouts654.html",
    "/workouts/quick": "workout_quick659.html",
    "/food": "food.html",
    "/doses": "doses.html",
    "/vitals": "vitals.html",
    "/vials": "vials.html",
    "/purchases": "purchases.html",
    "/coas": "coas.html",
    "/labs": "labs.html",
}


def read(name):
    return (TPL / name).read_text(encoding="utf-8")


def test_696_all_nine_pages_load_one_scoped_style_and_compile():
    env = Environment()
    for file in PAGES.values():
        html = read(file)
        asset = ("tracker-action-flow738.css?v=738"
                 if file in ("workouts654.html", "workout_quick659.html")
                 else "tracker-integrated-flow696.css?v=696")
        assert html.count(asset) == 1, file
        env.parse(html)
    css = CSS.read_text(encoding="utf-8")
    assert css.count("{") == css.count("}")
    assert "table.ux673-card-table" not in css
    assert "tracker-vial-jumps603" in css
    composite = (ROOT / "app/static/css/tracker-action-flow738.css").read_text()
    assert composite.endswith(css.rstrip() + "\n")


def test_696_primary_workout_finish_is_unambiguous_and_legacy_is_preserved():
    for file, action in (
        ("workouts654.html", "/workouts/finish"),
        ("workout_quick659.html", "/workouts/quick/finish"),
    ):
        html = read(file)
        forms = re.findall(
            rf'<form method="post" action="{re.escape(action)}" '
            r'class="tracker-flow696-finish">(.*?)</form>',
            html, re.S,
        )
        assert len(forms) == 1, file
        form = forms[0]
        assert form.count('formaction="/workouts/finish-review"') == 1
        assert form.count(">Finish &amp; Review</button>") == 1
        assert form.count(">Finish Workout</button>") == 1
        assert form.index("Finish &amp; Review") < form.index("<details>")
        assert "<summary>Other finish option</summary>" in form
    quick = read("workout_quick659.html")
    assert 'id="workout659-save"' in quick
    assert 'action="/workouts/quick/sets"' in quick
    assert 'id="workout659-rest-start"' in quick


def test_696_food_dose_and_vitals_keep_exact_recording_workflows():
    food, doses, vitals = (read(p) for p in (
        "food.html", "doses.html", "vitals.html",
    ))
    assert 'food424-actions food-mobile-actions602 ux673-food-primary' in food
    assert '<details class="tracker-flow696-guide">' in food
    for anchor in ("#food-quick-log", "#food-add", "#food-water", "#food-recorded"):
        assert f'href="{anchor}"' in food
    assert 'action="/food/water"' in food
    assert 'id="food-quick-log"' in food
    assert 'hx-post="/doses"' in doses
    assert 'id="calendar-vial-picker"' in doses
    assert 'id="dose-history"' in doses
    assert 'aria-label="Dose entry shortcuts"' in doses
    assert 'id="dose-repeat-notice"' in doses
    assert 'action="/vitals"' in vitals
    assert 'id="quick-vitals-entry"' in vitals
    for name in ("weight", "systolic", "diastolic", "pulse"):
        assert f'name="{name}"' in vitals
    assert 'href="/exports/vitals.csv"' in vitals
    assert 'class="tracker-flow696-guide"' in vitals


def test_696_vials_keep_single_nav_and_every_original_destination():
    html = read("vials.html")
    start = html.index('<h1>Vials</h1>')
    stop = html.index('<form method="get"', start)
    nav = html[start:stop]
    assert nav.count('<nav class="tracker-vial-jumps603"') == 1
    assert '<summary>More inventory tools</summary>' in nav
    for href in (
        "#tracker-vials-sortable", "#tracker-vial-find-panel",
        "#bulk-selection-toolbar", "#tracker-inventory-reports",
        "#tracker-vial-lifecycle", "/purchases#new-purchase",
        "/inventory-intelligence", "/inventory-alerts", "/reconciliation",
    ):
        assert nav.count(f'href="{href}"') == 1, href
    assert 'id="bulk-vials"' in html
    assert 'id="tracker-vials-sortable"' in html


def test_696_new_purchase_form_is_visible_before_history():
    html = read("purchases.html")
    assert html.index('id="new-purchase"') < html.index('id="purchase-history"')
    assert html.count('form method="post" action="/purchases"') == 1
    assert html.count('name="submission_token"') == 1
    assert 'id="purchase-review-guide618"' in html
    assert 'data-purchase-search' in html
    assert 'data-purchase-export' in html
    assert 'id="purchase-history-table"' in html
    assert "An order alone adds no stock" in html


def test_696_coa_search_preserves_vial_and_document_links():
    html = read("coas.html")
    assert 'data-flow696-coas' in html
    assert 'data-flow696-search' in html
    assert 'data-flow696-reset' in html
    assert 'data-flow696-coa-row' in html
    assert 'href="/coa-test-types"' in html
    assert 'href="/coas/new"' in html
    assert 'href="/coas/{{ c.id }}"' in html
    assert 'c.all_vials' in html
    assert 'c.attachments' in html
    assert '<table class="ux673-card-table' in html
    for label in ("COA", "Compound", "Lab", "Test date",
                  "Purity", "Review", "Document", "Actions"):
        assert f'data-label="{label}"' in html
    script = JS.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "localStorage",
                      "sessionStorage", "requestSubmit("):
        assert forbidden not in script
    assert "item.row.hidden = !show" in script


def test_696_lab_reports_first_with_unmodified_trend_controls():
    html = read("labs.html")
    assert html.index('id="labs-reports-section"') < html.index('id="lab-trends-section"')
    assert 'id="labs-report-search"' in html
    assert 'id="labs-trend-controls"' in html
    assert 'id="labs-reports-table"' in html
    assert 'href="/labs/new"' in html
    assert 'href="/labs/compare"' in html
    assert 'href="#labs-reports-section"' in html
    assert 'href="#lab-trends-section"' in html
    assert 'data-labs-trend-card' in html
    assert 'data-labs-report-row' in html


def test_696_every_existing_page_returns_200_without_writes():
    with TestClient(app, follow_redirects=False) as client:
        for path in PAGES:
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            asset = ("tracker-action-flow738.css?v=738"
                     if path in ("/workouts", "/workouts/quick")
                     else "tracker-integrated-flow696.css?v=696")
            assert asset in response.text, path
    # All new behavior is GET navigation or client-only filtering;
    # POST endpoints were not changed and are never called here.
