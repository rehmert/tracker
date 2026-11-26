"""Release 776: Google Tasks stays visible in everyday-only navigation mode."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


def test_776_google_tasks_is_default_everyday_navigation_destination():
    focus = (APP / "static/tracker_focus.js").read_text(encoding="utf-8")
    from app.navigation import NAVIGATION
    essential = {href for _, _, links in NAVIGATION for href, _, primary in links if primary}
    assert "/integrations/google-tasks" in essential
    assert "/regimen" in essential
    assert "item.dataset.navPrimary === 'yes'" in focus
    assert "let enabled = true;" in focus


def test_776_navigation_cache_refresh_and_sidebar_link_survive():
    base = (APP / "templates/base.html").read_text(encoding="utf-8")
    Environment().parse(base)
    assert '/static/tracker_focus.js?v=793' in base
    assert 'data-nav-primary=' in base
    assert 'id="sidebar-open"' in base


def test_776_existing_focus_preferences_are_preserved():
    focus = (APP / "static/tracker_focus.js").read_text(encoding="utf-8")
    assert "const KEY = 'tracker.navigation.focus.v1';" in focus
    assert "if (saved !== null) enabled = saved === 'true'" in focus
    assert "active.has(href)" in focus
    assert "localStorage" in focus
    assert "new MutationObserver" in focus
