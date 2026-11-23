"""Release 758: default 40x20 single labels, full PNG/SVG content parity."""
import inspect
import re
import struct
import zlib

import pytest

from app import vial_labels423 as base
from app import vial_label_rotation431 as rotated
from app import vial_label_sheets447 as sheets
from app.routers import vials as routes
from app.vial_label_compact758 import geometry758, is_compact758
from app.vial_label_fourline758 import validate_four_line_fit758

PRE = ["TESAMORELIN / BLACKFIN SUPPLY / 11/05/26", "10mg / 11.2mg"]
POST = PRE + ["11/23/26 / 2mL BAC / 5mg/mL", "1.4mg = 28 units"]


def _png_pixels(data):
    width, height = struct.unpack(">II", data[16:24])
    pos = 8
    encoded = bytearray()
    while pos < len(data):
        count = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        if kind == b"IDAT":
            encoded.extend(data[pos + 8:pos + 8 + count])
        pos += count + 12
        if kind == b"IEND":
            break
    raw = zlib.decompress(encoded)
    assert len(raw) == (width + 1) * height
    assert all(raw[y * (width + 1)] == 0 for y in range(height))
    return width, height, raw


@pytest.mark.parametrize("lines", [PRE, POST])
def test_758_default_40x20_has_all_lines_in_png_and_svg(lines):
    validate_four_line_fit758(lines, "40x20", 0)
    assert is_compact758(lines, "40x20")
    w, h, cols, rows = base._panel_size("40x20")
    assert (cols, rows) == (1, 1)
    assert (w, h) == (base.pixels(40), base.pixels(20))
    png = rotated.png_bytes(lines, "40x20", 0)
    svg = rotated.svg_bytes(lines, "40x20", 0).decode("utf-8")
    assert all(s in svg for s in lines)
    assert svg.count('class="tracker-compact-label758"') == 1
    width, height, raw = _png_pixels(png)
    assert (width, height) == (w, h)
    dots = geometry758(lines, w, h, base.FONT)
    expected = {(x, y + delta) for x, y in dots for delta in (0, 1)}
    actual = {
        (x, y)
        for y in range(2, h - 2)
        for x in range(2, w - 2)
        if raw[y * (w + 1) + 1 + x] == 0
    }
    assert actual == expected
    path = re.search(r'<path d="([^"]+)"', svg)
    assert path is not None
    assert set((int(x), int(y)) for x, y in
               re.findall(r"M(\d+) (\d+)h1v2h-1z", path.group(1))) == set(dots)


def test_758_all_four_http_route_defaults_are_single_40x20():
    for fn in (routes.vial_labels423, routes.vial_labels423_export,
               routes.vial_label_sheets447_page,
               routes.vial_label_sheets447_download):
        assert inspect.signature(fn).parameters["layout"].default == "40x20"
    assert base.LAYOUTS["40x20"] == (40, 20, 1, 1)
    assert len(sheets.paginate447([PRE], "40x20")) == 1
    assert len(sheets.paginate447([PRE, POST], "40x20")) == 2
    assert len(sheets.paginate447([PRE, POST], "30x15x2")) == 1


def test_758_40x20_default_is_selected_in_both_label_forms():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    single = (root / "app/templates/vial_labels423.html").read_text()
    multi = (root / "app/templates/vial_label_sheets447.html").read_text()
    assert '40 × 20 mm — single sticker (default)' in single
    assert '40 × 20 mm — single sticker (default)' in multi
    assert "30 × 15 mm — single sticker (recommended)" not in single + multi
    assert 'value="30x15x2"' in single and 'value="30x15x2"' in multi


def test_758_overlong_default_label_rejected_instead_of_cropped():
    very_long = PRE.copy()
    very_long[0] = "COMPOUND / " + ("EXTREMELY LONG VENDOR NAME " * 4) + "/ 11/05/26"
    with pytest.raises(ValueError, match="too long"):
        validate_four_line_fit758(very_long, "40x20", 0)
    with pytest.raises(ValueError, match="normal orientation"):
        validate_four_line_fit758(POST, "40x20", 90)
    with pytest.raises(ValueError, match="Character"):
        validate_four_line_fit758(["☃ / VENDOR / 11/05/26", PRE[1]], "40x20", 0)


def test_758_legacy_content_keeps_40x20_unchanged():
    old = ["TEST PEPTIDE", "10 MG", "VIAL #8", "MIX: 2026-11-23"]
    assert not is_compact758(old, "40x20")
    assert rotated.png_bytes(old, "40x20", 0) == base.png_bytes(old, "40x20")
