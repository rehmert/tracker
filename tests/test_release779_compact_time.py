"""Release 779: colon-free military time is usable across the shared entry UI."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_779_shared_clock_and_legacy_browser_behavior():
    subprocess.run(
        ["node", "scripts/tracker-time24-check779.cjs"],
        cwd=ROOT, check=True, timeout=45,
    )
    subprocess.run(
        ["node", "scripts/tracker-time24-check371.cjs"],
        cwd=ROOT, check=True, timeout=45,
    )


def test_779_both_time_adapters_preserve_named_server_fields():
    base = (ROOT / "app/templates/base.html").read_text()
    shared = (ROOT / "app/static/js/tracker-time24-global713.js").read_text()
    legacy = (ROOT / "app/static/js/tracker-time24-371.js").read_text()
    assert "tracker-time24-global713.js?v=779" in base
    assert 'input[type="datetime-local"], input[type="time"]' in shared
    assert "original.value = next" in shared
    assert "original.hidden = true" in shared
    assert "clock.name =" not in shared
    assert "date.name =" not in shared
    assert "normalizeClock(clock.value)" in shared
    assert "normalizeClock(time.value)" in legacy
    assert "form.addEventListener('submit', formatVisibleClock)" in shared
    assert "form.addEventListener('submit', formatVisibleTime)" in legacy


def test_779_legacy_script_urls_are_cache_busted():
    for page in ("doses", "dose_edit", "vitals", "vitals_edit",
                 "blend_dose_edit711"):
        source = (ROOT / "app/templates" / f"{page}.html").read_text()
        assert "tracker-time24-371.js?v=779" in source


def test_779_chromium_real_forms_mobile_and_desktop():
    """Native named fields must receive valid HH:MM before HTML submission."""
    from playwright.sync_api import sync_playwright

    script = (ROOT / "app/static/js/tracker-time24-global713.js").read_text()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in (390, 1280):
                page = browser.new_page(viewport={"width": width, "height": 844})
                page.set_content("""
                <html><body>
                <form id="actual" action="/fake" method="post">
                  <label>Schedule
                    <input id="native-clock" type="time" name="at_time"
                      value="07:15" required>
                  </label>
                  <label>Logged
                    <input id="native-stamp" type="datetime-local"
                      name="logged_at" value="2026-11-24T20:30" required>
                  </label>
                  <button>Save</button>
                </form>
                </body></html>
                """)
                page.add_script_tag(content=script)
                clocks = page.locator("input.tracker-time24-input713")
                assert clocks.count() == 2
                clocks.nth(0).fill("0730")
                clocks.nth(0).blur()
                assert clocks.nth(0).input_value() == "07:30"
                assert page.locator("#native-clock").input_value() == "07:30"

                clocks.nth(0).fill("930")
                clocks.nth(0).blur()
                assert clocks.nth(0).input_value() == "09:30"
                assert page.locator("#native-clock").input_value() == "09:30"

                clocks.nth(1).fill("2130")
                clocks.nth(1).blur()
                assert clocks.nth(1).input_value() == "21:30"
                assert page.locator("#native-stamp").input_value() == (
                    "2026-11-24T21:30"
                )

                body = page.locator("#actual").evaluate("""form => {
                    const entries = Object.fromEntries(new FormData(form));
                    return entries;
                }""")
                assert body == {
                    "at_time": "09:30", "logged_at": "2026-11-24T21:30"
                }

                clocks.nth(0).fill("2360")
                assert not clocks.nth(0).evaluate("el => el.checkValidity()")
                assert page.locator("#native-clock").input_value() == ""

                clocks.nth(0).fill("2359")
                assert page.locator("#native-clock").input_value() == "23:59"
                page.close()
        finally:
            browser.close()
