"""Navigation productivity must preserve sidebar identities and pagination."""
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "app/templates/base.html").read_text()
NAV = (ROOT / "app/static/nav_sort.js").read_text()
FINDER = (ROOT / "app/static/page_finder.js").read_text()
EXTRA = (ROOT / "app/static/js/tracker-nav-productivity.js").read_text()


def test_navigation_controls_and_stable_identifiers():
    # An existing Health Timeline regression looks for "Page " as a
    # pagination indicator across the response. Keep global text distinct.
    assert "Page " not in BASE

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        for token in (
            'id="tracker-recent-pages"',
            'id="tracker-recent-list"',
            'id="tracker-find-current"',
            'id="tracker-copy-link"',
            'id="tracker-clear-recent"',
            'id="tracker-expand-nav"',
            'id="tracker-collapse-nav"',
            'data-section="Inventory tools"',
            'data-nav-key="/reconstitution-calculator"',
            "tracker-nav-productivity.js?v=20261103-release",
        ):
            assert token in response.text


def test_browser_local_shortcuts_and_keyboard_access():
    assert "tracker.navigation.recent-pages.v1" in EXTRA
    assert "window.location.pathname" in EXTRA
    assert "window.location.href" in EXTRA
    assert "localStorage.setItem" in EXTRA
    assert "input.focus()" in EXTRA
    assert "setAll(true)" in EXTRA
    assert "setAll(false)" in EXTRA
    assert "fetch(" not in EXTRA


def test_preferences_and_search_use_existing_keys():
    assert "tracker-grouped-nav-v1" in NAV
    assert "tracker-nav-order-v1" in NAV
    assert "window.confirm(" in NAV
    assert "aria-activedescendant" in FINDER
    assert "page-finder-summary" in FINDER
    assert "items: pages.slice(0, 12)" in FINDER
