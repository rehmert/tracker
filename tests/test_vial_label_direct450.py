"""Release 450: unarchived, directly downloadable vial PNG and SVG strips."""
import io
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import vial_labels423 as original
from app import vial_label_sheets447 as sheets
from app import vial_label_direct450 as direct
from app.routers import vials


def vial(ident, *, mixed=False):
    return SimpleNamespace(
        id=ident,
        compound=SimpleNamespace(name=f"Compound-{ident}"),
        content_value=10.0,
        content_unit="mg",
        label=f"SAMPLE-{ident}",
        lot=f"LOT-{ident}",
        cap_color="blue",
        reconstituted_on=date(2026, 11, 5) if mixed else None,
        volume_ml=2.0 if mixed else None,
        beyond_use_on=date(2026, 11, 20) if mixed else None,
        expires_on=None,
    )


def pages_for(layout, count=5):
    return sheets.paginate447(
        sheets.label_panels447([vial(i) for i in range(1, count + 1)]),
        layout,
    )


@pytest.mark.parametrize("layout", tuple(original.LAYOUTS))
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_direct_png_multiple_pages_are_exact_unscaled_stacked_stickers(
    layout, rotation,
):
    pages = pages_for(layout, 5)
    width, height, cols, rows = original._panel_size(layout)
    expected_width, expected_height = width * cols, height * rows
    blob = direct.direct_download450(pages, layout, rotation, "png")
    assert blob.startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10)))
    assert not zipfile.is_zipfile(io.BytesIO(blob))
    assert struct.unpack(">II", blob[16:24]) == (
        expected_width, expected_height * len(pages),
    )
    assert b"pHYs" in blob
    offset = blob.index(b"pHYs") + 4
    assert struct.unpack(">II", blob[offset:offset + 8]) == (7992, 7992)
    pixels = sheets._decode_original_png447(
        blob, expected_width, expected_height * len(pages)
    )
    for idx, page in enumerate(pages):
        before = sheets.png_sheet447(page, layout, rotation)
        reference = sheets._decode_original_png447(
            before, expected_width, expected_height
        )
        start = idx * expected_width * expected_height
        end = start + expected_width * expected_height
        assert pixels[start:end] == reference


@pytest.mark.parametrize("layout", tuple(original.LAYOUTS))
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_direct_svg_is_single_document_with_physical_dimensions_and_all_strips(
    layout, rotation,
):
    pages = pages_for(layout, 5)
    blob = direct.direct_download450(pages, layout, rotation, "svg")
    assert blob.startswith(b"<svg ")
    assert not zipfile.is_zipfile(io.BytesIO(blob))
    tree = ET.fromstring(blob)
    mm_w, mm_h = sheets.physical_size447(layout)
    assert tree.attrib["width"] == f"{mm_w}mm"
    assert tree.attrib["height"] == f"{mm_h * len(pages)}mm"
    expected_w = original.pixels(original.LAYOUTS[layout][0]) * original.LAYOUTS[layout][2]
    expected_h = original.pixels(original.LAYOUTS[layout][1]) * original.LAYOUTS[layout][3]
    assert tree.attrib["viewBox"] == f"0 0 {expected_w} {expected_h * len(pages)}"
    svg = blob.decode("utf-8")
    for idx in range(len(pages)):
        assert f'transform="translate(0 {idx * expected_h})"' in svg
    # The small layout may truncate long vial ID lines, so validate full
    # ordered rendering with independently generated source strip contents.
    for page in pages:
        original_xml = sheets.svg_sheet447(page, layout, rotation).decode("utf-8")
        assert original_xml.split(">", 1)[1].removesuffix("</svg>") in svg


@pytest.mark.parametrize("fmt", ("png", "svg"))
@pytest.mark.parametrize("layout", tuple(original.LAYOUTS))
def test_one_strip_is_downloadable_as_file_without_zip(fmt, layout):
    pages = pages_for(layout, 5)
    first = direct.direct_download450(pages, layout, 90, fmt, sheet=1)
    last = direct.direct_download450(
        pages, layout, 90, fmt, sheet=len(pages)
    )
    assert first != last
    assert not zipfile.is_zipfile(io.BytesIO(first))
    if fmt == "png":
        assert first == sheets.png_sheet447(pages[0], layout, 90)
        assert last == sheets.png_sheet447(pages[-1], layout, 90)
    else:
        assert first.startswith(b"<svg ")
        assert last.startswith(b"<svg ")
        assert ET.fromstring(first).attrib["height"].endswith("mm")


def test_single_sheet_all_export_matches_one_strip():
    pages = pages_for("10x20x4", 2)
    assert len(pages) == 1
    for fmt in ("png", "svg"):
        assert direct.direct_download450(
            pages, "10x20x4", 270, fmt
        ) == direct.direct_download450(
            pages, "10x20x4", 270, fmt, sheet=1
        )


@pytest.mark.parametrize("fmt", ("png", "svg"))
def test_invalid_sheet_is_rejected_not_silently_substituted(fmt):
    pages = pages_for("30x15x2", 3)
    for sheet in (-1, 3, True, 1.5):
        with pytest.raises(ValueError, match="strip"):
            direct.direct_download450(pages, "30x15x2", 0, fmt, sheet)
    with pytest.raises(ValueError, match="format"):
        direct.direct_download450(pages, "30x15x2", 0, "zip")
    with pytest.raises(ValueError, match="layout"):
        direct.direct_download450(pages, "nope")
    with pytest.raises(ValueError, match="Rotation"):
        direct.direct_download450(pages, "30x15x2", 45)


@pytest.mark.parametrize("fmt,mime,signature", (
    ("png", "image/png", bytes((137, 80, 78, 71, 13, 10, 26, 10))),
    ("svg", "image/svg+xml", b"<svg "),
))
def test_download_route_responds_with_actual_file_not_zip(
    monkeypatch, fmt, mime, signature,
):
    pages = pages_for("10x20x4", 5)
    monkeypatch.setattr(
        vials, "_label_job447",
        lambda db, ids, layout, phase, rotation, copies: (
            [1, 2, 3, 4, 5], pages
        ),
    )
    response = vials.vial_label_sheets447_download(
        ids="1,2,3,4,5", layout="10x20x4", phase="auto",
        rotation=90, copies=1, fmt=fmt, sheet=0, db=object(),
    )
    assert response.body.startswith(signature)
    assert response.media_type == mime
    assert not zipfile.is_zipfile(io.BytesIO(response.body))
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    filename = response.headers["content-disposition"]
    assert filename.startswith('attachment; filename="vial-labels-')
    assert filename.endswith(f"-all-strips.{fmt}\"")
    assert ".zip" not in filename

    strip = vials.vial_label_sheets447_download(
        ids="1,2,3,4,5", layout="10x20x4", phase="auto",
        rotation=90, copies=1, fmt=fmt, sheet=2, db=object(),
    )
    assert strip.media_type == mime
    assert strip.headers["content-disposition"].endswith(
        f"-strip-002.{fmt}\""
    )
    assert not zipfile.is_zipfile(io.BytesIO(strip.body))

    with pytest.raises(HTTPException) as error:
        vials.vial_label_sheets447_download(
            ids="1,2,3,4,5", layout="10x20x4", phase="auto",
            rotation=90, copies=1, fmt=fmt, sheet=3, db=object(),
        )
    assert error.value.status_code == 422


def test_existing_scoped_routes_and_single_vial_export_unmodified():
    router = Path("app/routers/vials.py").read_text()
    assert "from ..vial_label_direct450 import direct_download450" in router
    assert "zip_sheets447(pages" not in router
    assert "db: Session = Depends(get_scoped_db390)" in router
    assert 'media = "image/svg+xml" if fmt == "svg" else "image/png"' in router
    assert '@router.get("/vials/{vid}/labels/export")' in router


def test_preview_has_plain_download_actions_for_full_run_and_each_strip():
    html = Path("app/templates/vial_label_sheets447.html").read_text()
    assert "Download All PNG Sheets (one file)" in html
    assert "Download All SVG Sheets (one file)" in html
    assert "Download strip {{ sheet.number }} PNG" in html
    assert "Download strip {{ sheet.number }} SVG" in html
    assert html.count("&amp;sheet={{ sheet.number }}") == 2
    assert "Download All PNG Sheets (ZIP)" not in html
    assert "Download All SVG Sheets (ZIP)" not in html
    assert 'class="sheet-downloads"' in html
    assert ".toolbar,.sheet-heading,.sheet-downloads{display:none!important}" in html
    assert "--label-preview-scale:3" in html
    assert "transform:scale(var(--label-preview-scale))" in html
