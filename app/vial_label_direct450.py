"""Release 450: directly downloadable SVG/PNG vial strips, never ZIP.

A complete label run can be downloaded as one vertically stacked image,
or any physical strip can be downloaded on its own. The original 203-DPI
PNG pixels and millimeter-sized sticker geometry are preserved.
"""

from __future__ import annotations

import struct
import zlib

from . import vial_labels423 as original
from . import vial_label_rotation431 as rotated
from . import vial_label_sheets447 as sheets


def _sheet_geometry(layout):
    if layout not in original.LAYOUTS:
        raise ValueError("Unsupported sheet layout")
    w_mm, h_mm, columns, rows = original.LAYOUTS[layout]
    return (
        w_mm * columns, h_mm * rows,
        original.pixels(w_mm) * columns,
        original.pixels(h_mm) * rows,
        columns * rows,
    )


def _validated_pages(pages, layout, rotation, sheet):
    rotated.validate_rotation(rotation)
    mm_w, mm_h, px_w, px_h, capacity = _sheet_geometry(layout)
    if not isinstance(pages, (list, tuple)) or not 1 <= len(pages) <= sheets.MAX_LABELS:
        raise ValueError("Invalid label sheets")
    if sum(len(page) for page in pages) > sheets.MAX_LABELS:
        raise ValueError("Too many labels")
    if any(not 1 <= len(page) <= capacity for page in pages):
        raise ValueError("Invalid sheet capacity")
    if type(sheet) is not int or sheet < 0 or sheet > len(pages):
        raise ValueError("Requested label strip does not exist")
    selected = [pages[sheet - 1]] if sheet else list(pages)
    return selected, (mm_w, mm_h, px_w, px_h)


def _strip_svg_body(page, layout, rotation):
    source = sheets.svg_sheet447(page, layout, rotation).decode("utf-8")
    opening = source.find(">")
    if opening < 0 or not source.startswith("<svg ") or not source.endswith("</svg>"):
        raise ValueError("Invalid generated SVG")
    return source[opening + 1:-len("</svg>")]


def direct_svg450(pages, layout, rotation=0, sheet=0):
    selected, (mm_w, mm_h, px_w, px_h) = _validated_pages(
        pages, layout, rotation, sheet,
    )
    count = len(selected)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{mm_w}mm" height="{mm_h * count}mm" '
        f'viewBox="0 0 {px_w} {px_h * count}">',
    ]
    for index, page in enumerate(selected):
        parts.append(f'<g transform="translate(0 {index * px_h})">')
        parts.append(_strip_svg_body(page, layout, rotation))
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")


def _chunk(kind, value):
    return (
        struct.pack(">I", len(value)) + kind + value
        + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
    )


def direct_png450(pages, layout, rotation=0, sheet=0):
    selected, (_, _, px_w, px_h) = _validated_pages(
        pages, layout, rotation, sheet,
    )
    # A single strip is returned unchanged, preserving its existing metadata
    # and exact bitmap. Multiple strips become one long 203-DPI PNG.
    if len(selected) == 1:
        return sheets.png_sheet447(selected[0], layout, rotation)

    # Preserve every row in source order. No rescaling or interpolation.
    raw = bytearray()
    for page in selected:
        data = sheets.png_sheet447(page, layout, rotation)
        bitmap = sheets._decode_original_png447(data, px_w, px_h)
        for row in range(px_h):
            start = row * px_w
            raw.append(0)  # PNG filter type: None
            raw.extend(bitmap[start:start + px_w])

    height = px_h * len(selected)
    ppm = round(original.DPI / 0.0254)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", px_w, height, 8, 0, 0, 0, 0))
        + _chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def direct_download450(pages, layout, rotation=0, fmt="png", sheet=0):
    if fmt not in sheets.FORMATS:
        raise ValueError("Unsupported label export format")
    if fmt == "png":
        return direct_png450(pages, layout, rotation, sheet)
    return direct_svg450(pages, layout, rotation, sheet)
