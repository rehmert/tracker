"""Regression contracts for scenario-first PK simulator UX."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_existing_scenario_routes_remain_unchanged():
    router = read("app/routers/pk.py")

    for route in (
        '@router.get("/scenarios")',
        '@router.post("/scenarios", status_code=201)',
        '@router.put("/scenarios/{sid}")',
        '@router.delete("/scenarios/{sid}")',
    ):
        assert route in router


def test_graph_refresh_is_race_safe():
    code = read("app/static/pk.js")

    assert "let graphRequestSequence = 0" in code
    assert "const sequence = ++graphRequestSequence" in code
    assert "sequence !== graphRequestSequence" in code
    assert "tracker:pk-graph-updated" in code
    assert "$('scenario').onchange=async" in code


def test_scenario_first_layout_and_live_preview():
    code = read(
        "app/static/js/tracker-pk-scenario-ux108.js"
    )

    assert "setup.after(card, graph)" in code
    assert "originalSelect.call(this, event)" in code
    assert "const originalSelect = scenario.onchange" in code
    assert "schedulePreview()" in code
    assert "350" in code
    assert "Unsaved settings" in code
    assert "wrapPersistence" in code

    # Scenario selection previews without a write.
    assert 'fetch(' not in code


def test_template_and_assets():
    html = read("app/templates/pk.html")

    assert (
        "tracker-pk-scenario-ux108.js?v=bundle108"
        in html
    )
    assert (
        "tracker-pk-scenario-ux108.css?v=bundle108"
        in html
    )
    assert 'id="scenario"' in html
    assert 'id="pkResults"' in html
    assert 'id="refresh"' in html

    Environment().parse(html)


def test_unchanged_pk_model():
    model = read("app/pk.py")
    assert "def exposure_at(" in model
    assert "def series(" in model
