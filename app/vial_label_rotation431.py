"""Rotate content inside each physical NIIMBOT sticker without rotating its strip.

All four orientations retain the existing 203-DPI sheet dimensions. Zero
rotation delegates to Release 423 for byte-for-byte compatibility.
"""

import html
import struct
import zlib

from . import vial_labels423 as original

ROTATIONS = (0, 90, 180, 270)


def validate_rotation(rotation):
    if type(rotation) is not int or rotation not in ROTATIONS:
        raise ValueError('Rotation must be 0, 90, 180, or 270 degrees')
    return rotation


def _physical_and_text_size(layout, rotation):
    angle = validate_rotation(rotation)
    width, height, columns, rows = original._panel_size(layout)
    text_width, text_height = (
        (height, width) if angle in (90, 270) else (width, height)
    )
    return width, height, columns, rows, text_width, text_height


def _selected_rotated(lines, width, height):
    """Keep glyphs inside the rotated content rectangle in both formats."""
    scale = 1 if width < 120 else 2
    capacity = max(1, (width - 8) // (6 * scale))
    return [line[:capacity] for line in original._selected(lines, width, height)]


def _svg_transform(x, y, width, height, rotation):
    if rotation == 90:
        return f'translate({x + width} {y}) rotate(90)'
    if rotation == 180:
        return f'translate({x + width} {y + height}) rotate(180)'
    return f'translate({x} {y + height}) rotate(270)'


def svg_bytes(lines, layout, rotation=0):
    w, h, cols, rows, tw, th = _physical_and_text_size(layout, rotation)
    if rotation == 0:
        return original.svg_bytes(lines, layout)

    width, height = w * cols, h * rows
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    font_size = 8 if tw < 120 else 13
    step = 11 if tw < 120 else 17
    selected = _selected_rotated(lines, tw, th)

    for row in range(rows):
        for col in range(cols):
            x, y = col * w, row * h
            parts.append(
                f'<rect x="{x + 1}" y="{y + 1}" '
                f'width="{w - 2}" height="{h - 2}" '
                'fill="none" stroke="#555" stroke-width="1"/>'
            )
            parts.append(
                f'<g transform="{_svg_transform(x, y, w, h, rotation)}">'
            )
            for index, value in enumerate(selected):
                parts.append(
                    f'<text x="4" y="{step * (index + 1)}" '
                    f'font-family="sans-serif" font-weight="bold" '
                    f'font-size="{font_size}" fill="black">'
                    f'{html.escape(value, quote=True)}</text>'
                )
            parts.append('</g>')
    parts.append('</svg>')
    return ''.join(parts).encode('utf-8')


def _chunk(kind, data):
    return (
        struct.pack('>I', len(data)) + kind + data
        + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    )


def png_bytes(lines, layout, rotation=0):
    w, h, cols, rows, tw, th = _physical_and_text_size(layout, rotation)
    if rotation == 0:
        return original.png_bytes(lines, layout)

    width, height = w * cols, h * rows
    canvas = bytearray([255]) * (width * height)

    def point(x, y):
        if 0 <= x < width and 0 <= y < height:
            canvas[y * width + x] = 0

    scale = 1 if tw < 120 else 2
    step = 11 if scale == 1 else 17
    selected = _selected_rotated(lines, tw, th)

    for row in range(rows):
        for col in range(cols):
            bx, by = col * w, row * h
            for x in range(bx, bx + w):
                point(x, by)
                point(x, by + h - 1)
            for y in range(by, by + h):
                point(bx, y)
                point(bx + w - 1, y)

            def rotated_point(lx, ly):
                if not (0 <= lx < tw and 0 <= ly < th):
                    return
                if rotation == 90:
                    px, py = w - 1 - ly, lx
                elif rotation == 180:
                    px, py = w - 1 - lx, h - 1 - ly
                else:
                    px, py = ly, h - 1 - lx
                point(bx + px, by + py)

            for index, line in enumerate(selected):
                x0, y0 = 4, 4 + index * step
                for j, char in enumerate(line):
                    x = x0 + j * 6 * scale
                    if x + 5 * scale > tw - 3:
                        break
                    for gy, bits in enumerate(
                        original.FONT.get(char, original.FONT['?'])
                    ):
                        for gx, bit in enumerate(bits):
                            if bit == '1':
                                for sy in range(scale):
                                    for sx in range(scale):
                                        rotated_point(
                                            x + gx * scale + sx,
                                            y0 + gy * scale + sy,
                                        )

    raw = b''.join(
        b'\0' + bytes(canvas[y * width:(y + 1) * width])
        for y in range(height)
    )
    ppm = round(original.DPI / 0.0254)
    return (
        b'\x89PNG\r\n\x1a\n'
        + _chunk(
            b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)
        )
        + _chunk(b'pHYs', struct.pack('>IIB', ppm, ppm, 1))
        + _chunk(b'IDAT', zlib.compress(raw, 9))
        + _chunk(b'IEND', b'')
    )
