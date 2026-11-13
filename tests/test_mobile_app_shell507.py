"""Release 507: Android-friendly app shell and install metadata contracts.

Static tests require no Android tooling, web browser or external network.
"""
import json
import struct
import zlib
from binascii import crc32
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app/templates/base.html"
STATIC = ROOT / "app/static"


def test_507_single_canonical_manifest_and_mobile_safe_viewport():
    html = BASE.read_text(encoding="utf-8")
    assert html.count('rel="manifest"') == 1
    assert "/static/tracker-dev.webmanifest" in html
    assert "/static/tracker.webmanifest" in html
    assert 'name="theme-color"' in html
    assert html.count('name="theme-color"') == 1
    assert 'viewport-fit=cover' in html
    assert 'tracker-mobile-shell507.css?v=507' in html
    assert 'tracker-mobile-shell507.js?v=603' in html
    assert html.index("tracker-compact-layout.css") < html.index(
        "tracker-mobile-shell507.css"
    )


def test_507_manifest_is_installable_and_uses_only_same_origin_paths():
    manifest = json.loads((STATIC / "tracker.webmanifest").read_text())
    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/mobile"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    icons = manifest["icons"]
    assert {
        (icon["src"], icon["sizes"], icon["type"]) for icon in icons
    } >= {
        ("/static/tracker-icon-192.png", "192x192", "image/png"),
        ("/static/tracker-icon-512.png", "512x512", "image/png"),
    }
    assert {item["url"] for item in manifest["shortcuts"]} == {
        "/mobile", "/quick-entry", "/doses", "/vitals",
    }
    assert all(item["url"].startswith("/") for item in manifest["shortcuts"])


def test_507_android_icons_have_real_png_headers_and_correct_dimensions():
    for dimension in (192, 512):
        raw = (STATIC / f"tracker-icon-{dimension}.png").read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        assert raw[12:16] == b"IHDR"
        assert struct.unpack(">II", raw[16:24]) == (dimension, dimension)
        assert raw[-12:-8] == b"\x00\x00\x00\x00"
        assert raw[-8:-4] == b"IEND"
        assert len(raw) > 1000


def test_507_png_chunks_and_pixel_stream_are_valid():
    for dimension in (192, 512):
        raw = (STATIC / f"tracker-icon-{dimension}.png").read_bytes()
        offset, image_stream, palette = 8, bytearray(), None
        while offset < len(raw):
            size = struct.unpack(">I", raw[offset:offset + 4])[0]
            kind = raw[offset + 4:offset + 8]
            data = raw[offset + 8:offset + 8 + size]
            stored_crc = struct.unpack(
                ">I", raw[offset + 8 + size:offset + 12 + size]
            )[0]
            assert crc32(kind + data) == stored_crc
            offset += 12 + size
            if kind == b"PLTE":
                palette = data
            if kind == b"IDAT":
                image_stream.extend(data)
            if kind == b"IEND":
                break
        assert offset == len(raw)
        assert palette is not None and len(palette) == 12
        pixels = zlib.decompress(image_stream)
        assert len(pixels) == dimension * (1 + dimension // 4)
        assert all(
            pixels[row * (1 + dimension // 4)] == 0
            for row in range(dimension)
        )


def test_507_phone_dock_exposes_workflows_and_reuses_real_sidebar():
    html = BASE.read_text(encoding="utf-8")
    assert 'class="tracker-mobile-dock"' in html
    assert 'aria-label="Mobile quick navigation"' in html
    assert 'id="tracker-mobile-more"' in html
    assert 'aria-controls="app-sidebar"' in html
    for route in ('href="/"', 'href="/mobile"', 'href="/quick-entry"',
                  'href="/doses"', 'href="/vitals"'):
        assert route in html
    assert 'aria-current="page"' in html
    assert 'id="sidebar-open"' in html

    javascript = (STATIC / "js/tracker-mobile-shell507.js").read_text()
    assert 'open.click()' in javascript
    assert 'observer.observe(shell' in javascript
    assert 'aria-expanded' in javascript
    assert 'focusin' in javascript
    assert 'focusout' in javascript
    assert "serviceWorker.register" not in javascript
    for forbidden in ("localStorage", "sessionStorage", "indexedDB"):
        assert forbidden not in javascript


def test_507_dock_is_mobile_only_and_respects_system_safe_areas():
    css = (STATIC / "css/tracker-mobile-shell507.css").read_text()
    assert ".tracker-mobile-dock { display: none; }" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (min-width: 761px)" in css
    assert "env(safe-area-inset-bottom" in css
    assert ".tracker-mobile-editing .tracker-mobile-dock" in css
    assert ".toast-region" in css
    assert "@media print" in css
