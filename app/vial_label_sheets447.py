"""Release 447: distinct-vial, multi-sticker NIIMBOT label sheets.

Preserves the three Release 423 physical layouts, 203-DPI grayscale PNG
format and Release 431 independent per-sticker content rotation. No direct
Bluetooth I/O, database writes, or invented inventory/expiry values.
"""

from __future__ import annotations

import html
import io
import re
import struct
import zlib
import zipfile

from . import vial_labels423 as original
from . import vial_label_rotation431 as rotated

MAX_VIALS = 120
MAX_LABELS = 240
MAX_COPIES = 4
PHASES = ("auto", "pre", "post")
FORMATS = ("svg", "png")
LAYOUTS = original.LAYOUTS
ROTATIONS = rotated.ROTATIONS


def parse_vial_ids447(raw):
    """Normalize a comma-separated list without adding missing/extra IDs."""
    if not isinstance(raw, str) or not raw or len(raw) > 1600:
        raise ValueError("Select between 1 and 120 vials")
    if not re.fullmatch(r"[1-9][0-9]*(,[1-9][0-9]*)*", raw):
        raise ValueError("Invalid vial selection")
    ids = [int(x) for x in raw.split(",")]
    if len(ids) > MAX_VIALS or any(uid > 2147483647 for uid in ids):
        raise ValueError("Select no more than 120 valid vials")
    if len(set(ids)) != len(ids):
        raise ValueError("A vial may be selected only once")
    # Numeric sorting makes print order stable even with cross-filter selection.
    return sorted(ids)


def validate_options447(layout, phase, rotation, copies):
    if layout not in LAYOUTS or phase not in PHASES:
        raise ValueError("Unsupported label layout or phase")
    rotated.validate_rotation(rotation)
    if type(copies) is not int or copies < 1 or copies > MAX_COPIES:
        raise ValueError("Copies must be 1 to 4 per vial")


def label_panels447(vials, phase="auto", copies=1):
    """Use current database values and fail if a requested phase is unavailable."""
    if phase not in PHASES or type(copies) is not int or not 1 <= copies <= MAX_COPIES:
        raise ValueError("Invalid label configuration")
    if not 1 <= len(vials) <= MAX_VIALS or len(vials) * copies > MAX_LABELS:
        raise ValueError("Too many labels for one print job")
    panels = []
    for vial in vials:
        applied = (
            ("post" if vial.reconstituted_on else "pre")
            if phase == "auto" else phase
        )
        try:
            lines = original.label_lines(vial, applied)
        except ValueError as exc:
            raise ValueError(f"Vial #{vial.id}: {exc}") from exc
        for _ in range(copies):
            panels.append(tuple(lines))
    return panels


def paginate447(panels, layout):
    if layout not in LAYOUTS:
        raise ValueError("Unsupported label layout")
    _, _, cols, rows = LAYOUTS[layout]
    capacity = cols * rows
    if not panels or len(panels) > MAX_LABELS:
        raise ValueError("Invalid label count")
    return [
        tuple(panels[i:i + capacity])
        for i in range(0, len(panels), capacity)
    ]


def physical_size447(layout):
    w, h, cols, rows = LAYOUTS[layout]
    return w * cols, h * rows


def _size447(layout, rotation):
    angle = rotated.validate_rotation(rotation)
    w, h, cols, rows = original._panel_size(layout)
    tw, th = (h, w) if angle in (90, 270) else (w, h)
    return w, h, cols, rows, tw, th


def svg_sheet447(panels, layout, rotation=0):
    """Render one distinct vial per sticker, padding unused stickers blank."""
    w, h, cols, rows, tw, th = _size447(layout, rotation)
    capacity = cols * rows
    if not 1 <= len(panels) <= capacity:
        raise ValueError("Invalid sheet capacity")
    if capacity == 1:
        return rotated.svg_bytes(panels[0], layout, rotation)

    width, height = w * cols, h * rows
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    size = 8 if tw < 120 else 13
    step = 11 if tw < 120 else 17
    for index in range(capacity):
        row, col = divmod(index, cols)
        x, y = col * w, row * h
        parts.append(
            f'<rect x="{x+1}" y="{y+1}" '
            f'width="{w-2}" height="{h-2}" '
            'fill="none" stroke="#555" stroke-width="1"/>'
        )
        if index >= len(panels):
            continue
        lines = (
            original._selected(panels[index], w, h)
            if rotation == 0
            else rotated._selected_rotated(panels[index], tw, th)
        )
        if rotation:
            parts.append(
                f'<g transform="{rotated._svg_transform(x, y, w, h, rotation)}">'
            )
        for offset, text in enumerate(lines):
            xval = 4 if rotation else x + 4
            yval = step * (offset + 1) if rotation else y + step * (offset + 1)
            parts.append(
                f'<text x="{xval}" y="{yval}" '
                'font-family="sans-serif" font-weight="bold" '
                f'font-size="{size}" fill="black">'
                f'{html.escape(str(text), quote=True)}</text>'
            )
        if rotation:
            parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")


def _decode_original_png447(data, expected_width, expected_height):
    """Decode the known dependency-free 8-bit grayscale/filter-0 renderer."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Unexpected source label image")
    offset = 8
    compressed = bytearray()
    width = height = None
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("Incomplete label image")
        payload = data[offset + 8:end - 4]
        if kind == b"IHDR":
            width, height, depth, color, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (width, height, depth, color, comp, filt, interlace) != (
                expected_width, expected_height, 8, 0, 0, 0, 0
            ):
                raise ValueError("Unexpected label PNG dimensions or encoding")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        offset = end
    if not compressed or width is None:
        raise ValueError("Missing label PNG pixels")
    raw = zlib.decompress(compressed)
    stride = width + 1
    if len(raw) != stride * height or any(raw[y * stride] != 0 for y in range(height)):
        raise ValueError("Unexpected label PNG pixel filters")
    return bytearray().join(
        raw[y * stride + 1:(y + 1) * stride] for y in range(height)
    )


def png_sheet447(panels, layout, rotation=0):
    """Use the existing single-vial renderer for every individual sticker.

    Cropping a generated sticker from the original strip preserves existing
    font, spacing, rotation and calibration. No third-party imaging library.
    """
    w, h, cols, rows, _, _ = _size447(layout, rotation)
    capacity = cols * rows
    if not 1 <= len(panels) <= capacity:
        raise ValueError("Invalid sheet capacity")
    if capacity == 1:
        return rotated.png_bytes(panels[0], layout, rotation)
    width, height = w * cols, h * rows
    # Empty sheet retains existing sticker borders, unused spaces stay empty.
    canvas = _decode_original_png447(
        original.png_bytes([], layout), width, height
    )
    for index, lines in enumerate(panels):
        source = _decode_original_png447(
            rotated.png_bytes(lines, layout, rotation), width, height
        )
        row, col = divmod(index, cols)
        x0, y0 = col * w, row * h
        for y in range(y0, y0 + h):
            start = y * width + x0
            canvas[start:start + w] = source[start:start + w]

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
        )

    raw = b"".join(
        b"\x00" + canvas[y * width:(y + 1) * width]
        for y in range(height)
    )
    ppm = round(original.DPI / 0.0254)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def zip_sheets447(pages, layout, rotation=0, fmt="png"):
    if fmt not in FORMATS or not pages or len(pages) > MAX_LABELS:
        raise ValueError("Unsupported sheet export")
    renderer = png_sheet447 if fmt == "png" else svg_sheet447
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for number, panels in enumerate(pages, 1):
            name = f"vial-sheet-{number:03d}.{fmt}"
            archive.writestr(
                name, renderer(panels, layout, rotation)
            )
    return output.getvalue()
