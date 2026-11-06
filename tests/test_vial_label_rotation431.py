"""Release 431: per-label print direction, fixed strip geometry, and routes."""

import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import vial_label_rotation431 as rotated
from app import vial_labels423 as original


def _pixel_rows(png):
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    width, height = struct.unpack('>II', png[16:24])
    offset = 8
    chunks = {}
    while offset < len(png):
        length = struct.unpack('>I', png[offset:offset + 4])[0]
        kind = png[offset + 4:offset + 8]
        chunks.setdefault(kind, []).append(png[offset + 8:offset + 8 + length])
        offset += 12 + length

    pixels = zlib.decompress(b''.join(chunks[b'IDAT']))
    stride = width + 1
    assert len(pixels) == height * stride
    assert all(pixels[y * stride] == 0 for y in range(height))
    rows = [pixels[y * stride + 1:y * stride + stride] for y in range(height)]
    return width, height, rows, chunks


@pytest.mark.parametrize('layout', tuple(original.LAYOUTS))
@pytest.mark.parametrize('angle', rotated.ROTATIONS)
def test_physical_sheet_and_dpi_stable_across_rotation(layout, angle):
    mm_width, mm_height, columns, panel_rows = original.LAYOUTS[layout]
    expected = (
        original.pixels(mm_width) * columns,
        original.pixels(mm_height) * panel_rows,
    )
    png = rotated.png_bytes(['F'], layout, angle)
    svg = rotated.svg_bytes(['F'], layout, angle)

    width, height, _, chunks = _pixel_rows(png)
    assert (width, height) == expected
    assert struct.unpack('>II', chunks[b'pHYs'][0][:8]) == (7992, 7992)

    root = ET.fromstring(svg)
    assert (int(root.attrib['width']), int(root.attrib['height'])) == expected
    assert root.attrib['viewBox'] == f'0 0 {width} {height}'
    if angle:
        groups = root.findall('{http://www.w3.org/2000/svg}g')
        assert len(groups) == columns * panel_rows
        assert all(
            f'rotate({angle})' in group.attrib['transform']
            for group in groups
        )


@pytest.mark.parametrize('layout', tuple(original.LAYOUTS))
def test_zero_rotation_is_byte_identical_to_release423(layout):
    lines = ['SAMPLE', '10 MG', 'VIAL #42', 'MIX: 2026-11-05']
    assert rotated.png_bytes(lines, layout, 0) == original.png_bytes(lines, layout)
    assert rotated.svg_bytes(lines, layout, 0) == original.svg_bytes(lines, layout)


@pytest.mark.parametrize('angle,pixel', (
    (90, (75, 4)),
    (180, (75, 155)),
    (270, (4, 155)),
))
def test_each_10x20x4_panel_rotates_glyph_as_requested(angle, pixel):
    _, _, rows, _ = _pixel_rows(
        rotated.png_bytes(['F'], '10x20x4', angle)
    )
    sticker_width = original.pixels(10)
    assert sticker_width == 80
    for col in range(4):
        assert rows[pixel[1]][col * sticker_width + pixel[0]] == 0


@pytest.mark.parametrize('angle', (None, '90', 45, -90, 360, True))
def test_invalid_rotation_is_rejected(angle):
    with pytest.raises(ValueError, match='Rotation'):
        rotated.png_bytes(['F'], '10x20x4', angle)
    with pytest.raises(ValueError, match='Rotation'):
        rotated.svg_bytes(['F'], '10x20x4', angle)


def test_rotated_svg_escapes_user_entered_text():
    svg = rotated.svg_bytes(
        ['<bad & value>'], '10x20x4', 90,
    ).decode()
    assert '&lt;bad &amp;' in svg
    assert '<bad & value>' not in svg


def test_selection_page_preserves_rotation(monkeypatch):
    from app.routers import vials

    monkeypatch.setattr(
        vials, '_get', lambda db, vid: SimpleNamespace(id=42),
    )
    monkeypatch.setattr(
        vials, 'render', lambda request, template, **kw: kw,
    )
    result = vials.vial_labels423(
        42, request=object(), layout='10x20x4', phase='pre',
        rotation=270, db=object(),
    )
    assert result['rotation'] == 270
    assert result['layout'] == '10x20x4'


def test_export_propagates_rotation_and_download_filename(monkeypatch):
    from app.routers import vials

    fake = SimpleNamespace(
        id=42, compound=SimpleNamespace(name='Compound'),
        content_value=10, content_unit='mg', label='test',
        reconstituted_on=None, volume_ml=None,
        beyond_use_on=None, expires_on=None, lot='', cap_color='',
    )
    monkeypatch.setattr(vials, '_get', lambda db, vid: fake)
    png = vials.vial_labels423_export(
        42, layout='10x20x4', phase='pre', fmt='png',
        rotation=90, download=1, db=object(),
    )
    assert _pixel_rows(png.body)[:2] == (320, 160)
    assert 'r90.png' in png.headers['content-disposition']

    svg = vials.vial_labels423_export(
        42, layout='10x20x4', phase='pre', fmt='svg',
        rotation=90, db=object(),
    )
    assert svg.body.count(b'rotate(90)') == 4
    assert 'inline' in svg.headers['content-disposition']


@pytest.mark.parametrize('angle', (45, 360, -90))
def test_invalid_query_angle_produces_422(angle):
    from app.routers import vials

    with pytest.raises(HTTPException) as page_error:
        vials.vial_labels423(
            42, request=object(), rotation=angle, db=object(),
        )
    assert page_error.value.status_code == 422

    with pytest.raises(HTTPException) as export_error:
        vials.vial_labels423_export(
            42, rotation=angle, db=object(),
        )
    assert export_error.value.status_code == 422


def test_template_propagates_rotation_to_preview_and_downloads():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/templates/vial_labels423.html').read_text()
    assert 'name="rotation"' in source
    assert source.count('&amp;rotation={{ rotation }}') == 3
    for angle in rotated.ROTATIONS:
        assert f'value="{angle}"' in source
