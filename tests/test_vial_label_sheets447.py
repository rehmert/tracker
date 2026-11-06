"""Release 447: multi-vial NIIMBOT label sheet source and route regressions."""

import io
import struct
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from markupsafe import Markup

from app import vial_labels423 as original
from app import vial_label_rotation431 as rotated
from app import vial_label_sheets447 as sheets
from app.routers import vials
from app.scoped_db390 import get_scoped_db390


def vial(ident, *, mixed=False, name=None):
    return SimpleNamespace(
        id=ident,
        compound=SimpleNamespace(name=name or f"Compound-{ident}"),
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


def test_selection_is_normalized_deterministically_and_never_duplicated():
    assert sheets.parse_vial_ids447("7,3,10") == [3, 7, 10]
    assert sheets.parse_vial_ids447("120") == [120]
    with pytest.raises(ValueError, match="only once"):
        sheets.parse_vial_ids447("2,2")
    for raw in ("", "0", "-1", "1,,2", "1, 2", "1;2", "01", "1&foo=2",
                "2147483648", "1," * 150):
        with pytest.raises(ValueError):
            sheets.parse_vial_ids447(raw)
    assert sheets.parse_vial_ids447(
        ",".join(str(i) for i in range(120, 0, -1))
    ) == list(range(1, 121))


def test_multi_label_auto_uses_each_vial_actual_reconstitution_state():
    rows = [vial(3), vial(7, mixed=True), vial(9)]
    panels = sheets.label_panels447(rows)
    assert len(panels) == 3
    assert "UNRECONSTITUTED" in panels[0]
    assert "MIX: 2026-11-05" in panels[1]
    assert "5 MG/ML" in panels[1]
    assert "BUD: 2026-11-20" in panels[1]
    assert "UNRECONSTITUTED" in panels[2]
    assert not any("BUD:" in line for line in panels[0])
    assert not any("BUD:" in line for line in panels[2])
    assert any("VIAL #7" in line for line in panels[1])


def test_panels_are_compatible_with_existing_svg_and_png_renderers():
    """Regression: _selected concatenates the first two rows with a list."""
    panels = sheets.label_panels447([vial(42), vial(43, mixed=True)])
    assert all(isinstance(panel, list) for panel in panels)
    for panel in panels:
        for layout in original.LAYOUTS:
            for angle in rotated.ROTATIONS:
                assert rotated.svg_bytes(panel, layout, angle).startswith(b"<svg")
                assert rotated.png_bytes(panel, layout, angle).startswith(
                    bytes((137, 80, 78, 71, 13, 10, 26, 10))
                )


def test_forced_mixed_phase_fails_closed_per_vial():
    with pytest.raises(ValueError, match=r"Vial #3.*reconstitution"):
        sheets.label_panels447([vial(3), vial(7, mixed=True)], "post")
    assert len(sheets.label_panels447([vial(3)], "pre")) == 1


@pytest.mark.parametrize(
    "layout,capacity,expected",
    [
        ("40x20", 1, 5),
        ("30x15x2", 2, 3),
        ("10x20x4", 4, 2),
    ],
)
def test_exactly_one_per_vial_paginates_across_strips(layout, capacity, expected):
    panels = sheets.label_panels447([vial(i) for i in range(1, 6)])
    pages = sheets.paginate447(panels, layout)
    assert len(pages) == expected
    assert sum(map(len, pages)) == 5
    assert all(1 <= len(page) <= capacity for page in pages)
    assert [line for page in pages for line in page] == panels
    assert len(set(tuple(line) for line in panels)) == 5


def test_copies_are_explicit_and_bounded_without_overrun():
    selection = [vial(1), vial(2)]
    panels = sheets.label_panels447(selection, copies=2)
    assert panels[0] == panels[1]
    assert panels[2] == panels[3]
    assert panels[0] != panels[2]
    for copies in (0, 5, -1, True, 1.5):
        with pytest.raises(ValueError):
            sheets.label_panels447(selection, copies=copies)
    with pytest.raises(ValueError, match="Too many labels"):
        sheets.label_panels447(
            [vial(i) for i in range(1, 121)], copies=3
        )


def test_multi_svg_has_distinct_vials_escapes_text_and_blank_final_slot():
    panels = sheets.label_panels447([
        vial(11, name="A<&B"),
        vial(12),
        vial(13),
    ])
    svg = sheets.svg_sheet447(panels, "10x20x4", 90).decode()
    assert svg.count('transform="translate(') == 3
    assert svg.count('<rect x=') == 4
    assert svg.count("VIAL #11") == 1
    assert svg.count("VIAL #12") == 1
    assert svg.count("VIAL #13") == 1
    assert "VIAL #14" not in svg
    assert "A&lt;&amp;B" in svg
    assert "A<&B" not in svg
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


@pytest.mark.parametrize("layout", ["40x20", "30x15x2", "10x20x4"])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_multi_png_panels_match_existing_single_vial_renderer_pixel_exactly(
    layout, rotation,
):
    w, h, cols, rows = original._panel_size(layout)
    capacity = cols * rows
    panels = sheets.label_panels447(
        [vial(i) for i in range(1, capacity + 1)]
    )
    multi = sheets.png_sheet447(panels, layout, rotation)
    assert multi.startswith(b"\x89PNG\r\n\x1a\n")
    dims = struct.unpack(">II", multi[16:24])
    assert dims == (w * cols, h * rows)
    full = sheets._decode_original_png447(
        multi, w * cols, h * rows
    )

    for idx, lines in enumerate(panels):
        one = sheets._decode_original_png447(
            rotated.png_bytes(lines, layout, rotation),
            w * cols, h * rows,
        )
        row, col = divmod(idx, cols)
        x0, y0 = col * w, row * h
        for yy in range(y0, y0 + h):
            a = yy * w * cols + x0
            assert full[a:a + w] == one[a:a + w]


def test_unused_png_stickers_match_unprinted_blank_stickers():
    layout = "10x20x4"
    w, h, cols, rows = original._panel_size(layout)
    one_panel = sheets.label_panels447([vial(9)])
    result = sheets._decode_original_png447(
        sheets.png_sheet447(one_panel, layout, 270), w * cols, h * rows
    )
    blank = sheets._decode_original_png447(
        original.png_bytes([], layout), w * cols, h * rows
    )
    for idx in range(1, cols * rows):
        row, col = divmod(idx, cols)
        x0, y0 = col * w, row * h
        for yy in range(y0, y0 + h):
            a = yy * w * cols + x0
            assert result[a:a + w] == blank[a:a + w]


@pytest.mark.parametrize("fmt", ["png", "svg"])
def test_zip_contains_one_export_per_sheet_with_correct_content(fmt):
    rows = [vial(i) for i in range(1, 6)]
    pages = sheets.paginate447(
        sheets.label_panels447(rows), "10x20x4"
    )
    payload = sheets.zip_sheets447(pages, "10x20x4", 90, fmt)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == [
            f"vial-sheet-001.{fmt}",
            f"vial-sheet-002.{fmt}",
        ]
        for index, sheet in enumerate(pages, 1):
            data = archive.read(f"vial-sheet-{index:03d}.{fmt}")
            assert data == (
                sheets.png_sheet447(sheet, "10x20x4", 90)
                if fmt == "png"
                else sheets.svg_sheet447(sheet, "10x20x4", 90)
            )


def test_sql_scoped_route_loads_every_existing_id_only_in_numeric_order(monkeypatch):
    class DB:
        def scalars(self, statement):
            return iter([vial(8), vial(3)])
    ids, pages = vials._label_job447(
        DB(), "8,3", "30x15x2", "auto", 0, 1,
    )
    assert ids == [3, 8]
    assert len(pages) == 1
    assert "VIAL #3" in pages[0][0][2]
    assert "VIAL #8" in pages[0][1][2]

    class Missing:
        def scalars(self, statement):
            return iter([vial(3)])
    with pytest.raises(HTTPException) as error:
        vials._label_job447(
            Missing(), "8,3", "30x15x2", "auto", 0, 1,
        )
    assert error.value.status_code == 404


def test_bad_requests_never_get_printable_or_downloadable_records():
    class DB:
        def scalars(self, statement):
            pytest.fail("Invalid request should not query database")
    for args in (
        ("", "10x20x4", "auto", 0, 1),
        ("1,1", "10x20x4", "auto", 0, 1),
        ("1", "unknown", "auto", 0, 1),
        ("1", "10x20x4", "unknown", 0, 1),
        ("1", "10x20x4", "auto", 45, 1),
        ("1", "10x20x4", "auto", 0, 0),
    ):
        with pytest.raises(HTTPException) as exc:
            vials._label_job447(DB(), *args)
        assert exc.value.status_code == 422


def test_routes_are_read_only_and_authorized_and_static_before_vial_detail():
    routes = [
        route for route in vials.router.routes
        if isinstance(route, APIRoute)
    ]
    paths = [route.path for route in routes]
    for path in (
        "/vials/labels/sheets",
        "/vials/labels/sheets/download",
    ):
        assert path in paths
        route = routes[paths.index(path)]
        assert route.methods == {"GET"}
        dependencies = {
            item.call for item in route.dependant.dependencies
        }
        assert get_scoped_db390 in dependencies
    assert paths.index("/vials/labels/sheets") < paths.index("/vials/{vid}")
    assert paths.index("/vials/labels/sheets/download") < paths.index("/vials/{vid}")


def test_page_preview_contains_one_svg_per_strip_and_no_store(monkeypatch):
    fake = [vial(1), vial(2), vial(3), vial(4), vial(5)]
    monkeypatch.setattr(
        vials, "_label_job447",
        lambda db, ids, layout, phase, rotation, copies: (
            [1, 2, 3, 4, 5],
            sheets.paginate447(sheets.label_panels447(fake), layout),
        ),
    )
    class FakeResponse:
        def __init__(self, context):
            self.context = context
            self.headers = {}
    monkeypatch.setattr(
        vials, "render",
        lambda request, template, **kw: FakeResponse(
            {"template": template, **kw}
        ),
    )
    result = vials.vial_label_sheets447_page(
        request=object(), ids="5,1,2,4,3", layout="10x20x4",
        phase="auto", rotation=90, copies=1, db=object(),
    )
    assert result.context["template"] == "vial_label_sheets447.html"
    assert result.context["selected_ids"] == "1,2,3,4,5"
    assert result.context["label_count"] == 5
    assert len(result.context["sheets"]) == 2
    assert isinstance(result.context["sheets"][0]["svg"], Markup)
    assert result.headers["Cache-Control"] == "private, no-store"
    assert result.headers["Referrer-Policy"] == "no-referrer"


def test_download_requires_supported_format_and_has_safe_headers(monkeypatch):
    fake = [vial(1), vial(2)]
    monkeypatch.setattr(
        vials, "_label_job447",
        lambda db, ids, layout, phase, rotation, copies: (
            [1, 2], sheets.paginate447(
                sheets.label_panels447(fake), layout,
            )
        ),
    )
    result = vials.vial_label_sheets447_download(
        ids="1,2", layout="30x15x2", phase="auto",
        rotation=90, copies=1, fmt="png", db=object(),
    )
    assert result.media_type == "image/png"
    assert result.headers["cache-control"] == "private, no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in result.headers["content-disposition"]
    assert result.headers["content-disposition"].endswith('.png"')
    assert result.body.startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10)))
    assert not zipfile.is_zipfile(io.BytesIO(result.body))

    with pytest.raises(HTTPException) as exc:
        vials.vial_label_sheets447_download(
            ids="1,2", fmt="pdf", db=object(),
        )
    assert exc.value.status_code == 422


def test_page_template_uses_exact_physical_print_sizes_and_selection_controls():
    template = Path("app/templates/vial_label_sheets447.html").read_text()
    vial_page = Path("app/templates/vials.html").read_text()
    script = Path("app/static/js/tracker-vial-label-sheets447.js").read_text()
    assert "@page{size:{{ width_mm }}mm {{ height_mm }}mm;margin:0}" in template
    assert "window.print()" in template
    assert 'name="ids"' in template
    assert 'name="phase"' in template
    assert 'name="rotation"' in template
    assert 'name="copies"' in template
    assert "Download All PNG Sheets (one file)" in template
    assert "Download All SVG Sheets (one file)" in template
    assert 'id="bulk-print-labels447"' in vial_page
    assert "tracker-vial-label-sheets447.js?v=447" in vial_page
    assert "tracker:bulk-selection-changed" in script
    assert "input.bulk-vial-check:checked" in script
    assert 'input[type="hidden"][name="vial_ids"]' in script
    assert "window.open(url" in script
