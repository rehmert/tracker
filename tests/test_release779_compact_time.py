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
