from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_focus_controls_present():
    base = (ROOT / 'app/templates/base.html').read_text()
    assert 'id="tracker-focus-toggle"' in base
    assert '/static/tracker_focus.js' in base
    assert '/static/tracker_focus.css' in base

def test_focus_preserves_critical_navigation_and_active_page():
    script = (ROOT / 'app/static/tracker_focus.js').read_text()
    for route in ('/mobile', '/calendar', '/doses', '/vials', '/workouts', '/food', '/vitals', '/labs', '/regimen'):
        assert repr(route) in script
    assert 'active.has(href)' in script
    assert 'localStorage' in script

def test_focus_defaults_on_for_new_browser_without_overriding_existing_choice():
    script = (ROOT / 'app/static/tracker_focus.js').read_text()
    assert "let enabled = true" in script
    assert "if (saved !== null) enabled = saved === 'true'" in script
