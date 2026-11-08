"""Release 509 DEV blue launcher regression tests.

Preserve the authenticated Tracker application while keeping the PWA
manifest and icon metadata publicly readable through /static.
"""
import json
import struct
import zlib
from binascii import crc32
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"


def test_dev_blue_manifest_uses_new_public_launcher_assets():
    manifest = json.loads((STATIC / "tracker-dev.webmanifest").read_text())
    assert manifest["name"] == "Tracker DEV"
    assert manifest["short_name"] == "Tracker DEV"
    assert manifest["theme_color"] == "#0754a6"
    assert manifest["start_url"] == "/mobile"
    assert manifest["display"] == "standalone"
    assert {(icon["src"], icon["sizes"]) for icon in manifest["icons"]} >= {
        ("/static/tracker-icon-dev-blue-192.png", "192x192"),
        ("/static/tracker-icon-dev-blue-512.png", "512x512"),
        ("/static/tracker-icon-dev-blue.svg", "any"),
    }
    assert all((STATIC / icon["src"].removeprefix("/static/")).is_file()
               for icon in manifest["icons"])
    # Installation metadata stays on the static route, not behind auth.
    html = (ROOT / "app/templates/base.html").read_text()
    assert "/static/tracker-dev.webmanifest" in html
    assert "tracker-icon-dev-blue.svg" in html
    assert "?v=5092" in html


def test_dev_blue_icons_decode_and_use_blue_palette():
    expected_palette = bytes((
        16, 36, 56, 247, 251, 255, 18, 101, 173, 7, 84, 166,
    ))
    for size in (192, 512):
        data = (STATIC / f"tracker-icon-dev-blue-{size}.png").read_bytes()
        assert data.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
        assert struct.unpack(">II", data[16:24]) == (size, size)
        assert data[25] == 3  # indexed color
        position = 8
        found_palette = False
        pixels = bytearray()
        while position < len(data):
            length = struct.unpack(">I", data[position:position + 4])[0]
            kind = data[position + 4:position + 8]
            chunk = data[position + 8:position + 8 + length]
            checksum = struct.unpack(
                ">I", data[position + 8 + length:position + 12 + length]
            )[0]
            assert crc32(kind + chunk) == checksum
            if kind == b"PLTE":
                assert chunk == expected_palette
                found_palette = True
            if kind == b"IDAT":
                pixels.extend(chunk)
            position += 12 + length
            if kind == b"IEND":
                break
        assert position == len(data)
        assert found_palette
        assert len(zlib.decompress(pixels)) == size * (1 + size // 4)


def test_dev_blue_svg_preserves_clear_dev_marking():
    svg = (STATIC / "tracker-icon-dev-blue.svg").read_text()
    assert 'aria-label="Tracker DEV"' in svg
    assert ">DEV</text>" in svg
    assert "#1686df" in svg and "#0754a6" in svg
    assert "#d58b2c" not in svg and "#70400b" not in svg
