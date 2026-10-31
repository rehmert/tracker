from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_focus_controls_present():
    base = (ROOT / 'app/templates/base.html').read_text()
    assert 'id="tracker-focus-toggle"' in base
    assert '/static/tracker_focus.js' in base
    assert '/static/tracker_focus.css' in base

def test_focus_preserves_critical_navigation_and_active_page():
    script = (ROOT / 'app/static/tracker_focus.js').read_text()
    for route in ('/doses', '/vials', '/protocols', '/labs', '/pk'):
        assert repr(route) in script
    assert 'active.has(href)' in script
    assert 'localStorage' in script
