"""Release 509: blue primary-accent palette across Android and desktop.

The older --teal CSS token is retained for backward compatibility with
existing components, but its assigned color is intentionally blue.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/app.css"
BASE = ROOT / "app/templates/base.html"


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[x:x+2], 16) / 255 for x in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in rgb
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    a, b = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def test_509_primary_theme_color_is_blue_in_all_light_and_dark_definitions():
    css = CSS.read_text()
    assert '--teal: #1265ad; --teal-ink: #ffffff;' in css
    assert '--teal:#1265ad; --teal-ink:#ffffff;' in css
    assert '--teal: #79b8f7; --teal-ink: #102438;' in css
    assert '--teal:#79b8f7; --teal-ink:#102438;' in css
    for old in ("#0f5c63", "#4fb3bd", "#0f766e", "#5eead4"):
        assert old not in css


def test_509_blue_accent_text_meets_normal_text_contrast_requirements():
    assert _contrast("#ffffff", "#1265ad") >= 4.5
    assert _contrast("#102438", "#79b8f7") >= 4.5


def test_509_blue_primary_theme_drives_navigation_and_mobile_capture():
    css = CSS.read_text()
    daily = (ROOT / "app/static/css/tracker-mobile-daily509.css").read_text()
    mobile_shell = (ROOT / "app/static/css/tracker-mobile-shell507.css").read_text()
    assert '.rail li a[aria-current] { background: var(--teal);' in css
    assert 'button.primary { background: var(--teal);' in css
    assert '.tracker-daily-mode button[aria-pressed="true"]{background:var(--teal,' in daily
    assert 'color: var(--teal, #1265ad);' in mobile_shell


def test_509_mobile_html_busts_cached_green_stylesheet():
    html = BASE.read_text()
    assert '/static/app.css?v=509-blue-accent' in html
    assert 'app.css?v=sidebar-scroll-20261031' not in html
    assert 'href="/static/tracker-dev.webmanifest' in html or (
        "/static/tracker-dev.webmanifest" in html
    )
