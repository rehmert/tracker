"""Release 559: everyday workflow and model cleanup regression tests."""

from pathlib import Path
import re

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"


def read(path):
    return (ROOT / path).read_text()


def test_release559_templates_compile():
    env = Environment()

    for name in (
        "dashboard.html",
        "mobile_today509.html",
        "quick_entry.html",
    ):
        env.parse((TEMPLATES / name).read_text())


def test_release559_daily_workflow_destinations_exist():
    routes = {
        "/mobile": "app/routers/mobile509.py",
        "/doses": "app/routers/doses.py",
        "/calendar": "app/routers/calendar.py",
        "/food": "app/routers/food.py",
        "/health-insights": "app/routers/health_insights.py",
        "/replenishment-review": "app/routers/replenishment_review.py",
        "/labs": "app/routers/labs.py",
    }

    for route, filename in routes.items():
        source = read(filename)

        assert (
            f'@router.get("{route}"' in source
            or f"@router.get('{route}'" in source
        ), (route, filename)

    assert 'id="food-quick-log"' in read(
        "app/templates/food.html"
    )

    assert 'id="food-water"' in read(
        "app/templates/food.html"
    )

    assert 'id="mobile-quick-vitals"' in read(
        "app/templates/mobile_today509.html"
    )

    assert 'id="quick-dose-entry"' in read(
        "app/templates/doses.html"
    )


def test_release559_dashboard_shortcuts():
    html = read("app/templates/dashboard.html")

    for url in (
        "/mobile",
        "/doses#quick-dose-entry",
        "/mobile#mobile-quick-vitals",
        "/food#food-quick-log",
        "/food#food-water",
        "/calendar",
        "/health-insights",
        "/replenishment-review",
    ):
        assert f'href="{url}"' in html

    assert html.count(
        'class="tracker-daily-flow559"'
    ) == 1


def test_release559_mobile_shortcuts():
    html = read("app/templates/mobile_today509.html")

    for url in (
        "/food#food-quick-log",
        "/food#food-water",
        "/health-insights",
        "/replenishment-review",
    ):
        assert f'href="{url}"' in html


def test_release559_quick_entry_search_contract():
    html = read("app/templates/quick_entry.html")

    for name in (
        "Log food",
        "Log water",
        "Review progress",
        "Review inventory needs",
    ):
        assert f"<strong>{name}</strong>" in html

    assert html.count("data-quick-action") >= 4
    assert "tracker-daily-flow559.css" in html


def test_release559_coa_model_definition_is_unique():
    source = read("app/models.py")

    assert len(
        re.findall(
            r"^    linked_coas: Mapped",
            source,
            re.M,
        )
    ) == 1

    assert source.count(
        "    def all_coas(self):"
    ) == 1


def test_release559_styles_are_scoped():
    css = read(
        "app/static/css/tracker-daily-flow559.css"
    )

    assert ".tracker-daily-flow559-links" in css
    assert ".tracker-daily-flow559-compact" in css


def test_release559_preserves_existing_dashboard_workflows():
    html = read("app/templates/dashboard.html")

    for url in (
        "/dose-workspace",
        "/calendar",
        "/vials",
        "/labs",
    ):
        assert f'href="{url}"' in html

    assert (
        'aria-label="Everyday workflow shortcuts"'
        in html
    )
