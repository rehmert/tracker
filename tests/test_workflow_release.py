from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dashboard_workflow_shortcuts():
    html = (ROOT / 'app/templates/dashboard.html').read_text()
    assert 'aria-label="Everyday workflow shortcuts"' in html
    for href in ('/dose-workspace', '/calendar', '/vials', '/labs'):
        assert f'href="{href}"' in html

def test_dose_workspace_search_is_read_only():
    html = (ROOT / 'app/templates/dose_workspace.html').read_text()
    js = (ROOT / 'app/static/tracker_dose_workspace.js').read_text()
    assert 'data-tracker-vial-row' in html
    assert 'tracker-vial-search' in html
    assert 'tracker-vial-no-matches' in html
    assert 'tracker_dose_workspace.js' in html
    assert "addEventListener('input', update)" in js
    assert 'fetch(' not in js
    assert 'XMLHttpRequest' not in js
