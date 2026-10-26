from pathlib import Path


def test_nav_sort_controls_are_inside_preferences():
    root = Path(__file__).parents[1] / "app"
    html = (root / "templates/base.html").read_text()
    sidebar = html.split('<nav class="rail"', 1)[1].split('</nav>', 1)[0]
    panel = html.split('id="workspace-settings-panel" class="workspace-settings-panel"', 1)[1].split('</section>', 1)[0]
    for control in ('nav-sort-mode', 'nav-edit-toggle', 'nav-reset', 'nav-sort-help'):
        assert control not in sidebar
        assert control in panel
    assert 'id="nav-sortable"' in sidebar
    assert 'workspace-nav-order' in panel


def test_nav_sort_storage_keys_unchanged():
    js = (Path(__file__).parents[1] / "app/static/nav_sort.js").read_text()
    assert 'tracker-nav-order-v1' in js
    assert 'tracker-nav-mode-v1' in js
