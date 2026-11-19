"""Release 695: consolidate Today recording links without changing data writes."""
from pathlib import Path
import re

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / "app/templates/mobile_today509.html"
QUICK = ROOT / "app/templates/quick_entry.html"
STYLES = ROOT / "app/static/css/tracker-productivity674.css"

ACTIONS = (
    "#mobile-quick-vitals",
    "/doses#quick-dose-entry",
    "/food#food-quick-log",
    "/food#food-water",
    "/workouts/quick",
    "/regimen#reg635-today",
    "/quick-entry",
)


def read(path):
    return path.read_text(encoding="utf-8")


def test_695_today_has_one_early_recording_bar_and_no_duplicate_row():
    html = read(TODAY)
    nav = re.search(
        r'<nav class="tracker-daily-actions" aria-label="Record today">(.*?)</nav>',
        html, re.S,
    )
    assert nav is not None
    assert html.count('class="tracker-daily-actions"') == 1
    assert html.count('class="ux674-dashboard"') == 1
    assert 'class="ux674-actions"' not in html
    hrefs = re.findall(r'<a\s[^>]*href="([^"]+)"', nav.group(1))
    assert tuple(hrefs) == ACTIONS
    assert html.index('class="tracker-daily-glance601"') < nav.start()
    assert nav.end() < html.index('class="ux674-dashboard"')
    assert 'href="/calendar"' in html
    assert 'href="/health-insights"' in html
    assert 'href="/replenishment-review"' in html
    assert 'href="/labs"' in html
    assert html.count('action="/vitals"') == 1
    assert 'name="return_to" value="mobile"' in html
    assert 'action="/doses"' not in html


def test_695_summary_reviews_are_contextual_and_read_only():
    html = read(TODAY)
    summary = html.split('class="ux674-dashboard"', 1)[1].split("</section>", 1)[0]
    for href in (
        "/food", "/inventory-data-quality",
        "/workouts/sessions/{{ daily674.last_workout.id }}/review",
        "/workouts",
    ):
        assert f'href="{href}"' in summary
    assert summary.count('class="ux695-summary-link"') == 4
    assert "<form" not in summary and "<button" not in summary
    assert 'href="/data-quality"' in summary
    assert 'daily674.last_workout' in summary
    css = read(STYLES)
    assert ".tracker-daily509 .ux695-summary-link" in css
    assert "min-height: 44px;" in css
    assert "grid-template-columns: repeat(2,minmax(0,1fr))" in css
    assert "tracker-productivity674.css?v=695" in html


def test_695_quick_entry_exposes_same_missing_recording_destinations():
    html = read(QUICK)
    for href, heading in (
        ("/workouts/quick", "Log workout set"),
        ("/regimen#reg635-today", "Log supplements / meds"),
    ):
        cards = re.findall(
            r'<a class="tracker-quick-entry-card"(.*?)</a>',
            html, re.S,
        )
        matches = [card for card in cards if f'href="{href}"' in card]
        assert len(matches) == 1
        assert 'data-quick-daily' in matches[0]
        assert 'data-quick-category="record"' in matches[0]
        assert f"<strong>{heading}</strong>" in matches[0]
    assert 'data-quick-search' in html
    assert 'data-quick-category="daily"' in html
    assert 'tracker-quick-entry.js?v=603' in html


def test_695_templates_compile():
    env = Environment()
    for path in (TODAY, QUICK):
        env.parse(read(path))


def test_695_existing_routes_render_without_recording():
    with TestClient(app, follow_redirects=False) as client:
        today = client.get("/mobile")
        quick = client.get("/quick-entry")
    assert today.status_code == 200
    assert quick.status_code == 200
    assert 'aria-label="Record today"' in today.text
    assert 'Daily Command Center' in today.text
    assert 'href="/workouts/quick"' in today.text
    assert 'href="/regimen#reg635-today"' in quick.text
    assert 'class="ux674-actions"' not in today.text
