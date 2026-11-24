"""Release 775: Google Tasks is a discoverable first-class navigation target.

Static template/Jinja and existing navigation contracts only; no user data.
"""
import ast
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
ICON_MAP = ROOT / "app/static/js/tracker-navigation-icons.js"
SORT = ROOT / "app/static/nav_sort.js"
URL = "/integrations/google-tasks"


def read(name):
    content = (TEMPLATES / name).read_text(encoding="utf-8")
    Environment().parse(content)
    return content


def _sidebar_sections(base):
    start = base.index("{% set sections = [") + len("{% set sections = ")
    end = base.index("%}", start)
    return ast.literal_eval(base[start:end].strip())


def test_775_google_tasks_has_unique_sidebar_nav_link_near_regimen():
    base = read("base.html")
    sections = _sidebar_sections(base)
    all_links = [link for _, group in sections for link in group]
    matches = [(url, title) for url, title in all_links if url == URL]
    assert matches == [(URL, "Google Tasks")]
    groups = dict(sections)
    health = groups["Health & Progress"]
    index = health.index(("/regimen", "Supplements & Medications"))
    assert health[index + 1] == (URL, "Google Tasks")
    assert "data-nav-key=\"{{ href }}\"" in base
    assert 'href="{{ href }}"' in base
    assert "path.startswith(href)" in base


def test_775_sidebar_inherits_search_favorites_and_mobile_navigation():
    base = read("base.html")
    nav = SORT.read_text(encoding="utf-8")
    assert 'id="app-sidebar"' in base
    assert 'id="sidebar-open"' in base
    assert 'id="nav-favorites"' in base
    assert 'data-favorite="{{ href }}"' in base
    assert 'id="nav-filter"' in base
    assert "localStorage" in nav
    assert "const defaults=" in nav
    assert 'querySelectorAll(\'[data-nav-key]\')' in nav


def test_775_icon_map_has_explicit_google_tasks_icon_and_cache_refresh():
    base = read("base.html")
    icon = ICON_MAP.read_text(encoding="utf-8")
    assert "'/integrations/google-tasks': 'clipboard'" in icon
    assert "/static/js/tracker-navigation-icons.js?v=34.38" in base


def test_775_protocol_and_regimen_google_tasks_actions_are_prominent():
    protocol = read("protocols.html")
    regimen = read("regimen635.html")
    assert protocol.count('href="' + URL + '"') == 1
    assert regimen.count('href="' + URL + '"') == 1
    assert 'class="ux-shortcuts"' in protocol
    assert 'class="ux-shortcuts"' in regimen
    assert '<a href="' + URL + '">Google Tasks settings</a>' in protocol
    assert '<a href="' + URL + '">Google Tasks settings</a>' in regimen
    assert 'Google Tasks sync settings</a></p>' not in protocol
    assert 'Google Tasks sync settings</a></p>' not in regimen


def test_775_settings_destination_and_batch_save_stay_intact():
    from app.routers.google_tasks769 import BASE, router
    assert BASE == URL
    methods = {
        (frozenset(route.methods), route.path)
        for route in router.routes
    }
    assert (frozenset({"GET"}), URL) in methods
    assert (frozenset({"POST"}), URL + "/titles") in methods
    page = read("google_tasks769.html")
    assert "Save all titles" in page
    assert 'action="' + URL + '/titles"' in page


def test_775_documented_batch_edit_guideline_is_preserved():
    policy = (ROOT / "docs/ux-batch-editing-guideline.md").read_text(
        encoding="utf-8"
    )
    assert "single Save all action" in policy
    assert "Commit the group atomically" in policy
