"""Release 423: dependency-free 203-DPI label output; no Bluetooth access."""

import html
import re
import struct
import unicodedata
import zlib

DPI = 203

# One physical sticker dimensions, columns, rows.
LAYOUTS = {
    '40x20': (40, 20, 1, 1),
    '50x30': (50, 30, 1, 1),
    '30x15': (30, 15, 1, 1),  # single sticker for 3 mL vials
    '30x15x2': (30, 15, 1, 2),
    '10x20x4': (10, 20, 4, 1),
}


def pixels(mm):
    return round(mm * DPI / 25.4)


def _plain(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = value.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', value).strip().upper()


def _number(value):
    return f'{value:g}'


def label_lines(vial, phase, *, dose_line=None, concentration_mg_ml=None):
    if phase not in ('pre', 'post'):
        raise ValueError('Invalid label phase')

    if phase == 'post' and not vial.reconstituted_on:
        raise ValueError(
            'Record the reconstitution date before printing a mixed label'
        )

    lines = [
        _plain(vial.compound.name),
        f'{_number(vial.content_value)} {_plain(vial.content_unit)}',
        f'VIAL #{vial.id} {_plain(vial.label)}',
    ]

    if phase == 'pre':
        lines += ['UNRECONSTITUTED']
    else:
        lines.append(f'MIX: {vial.reconstituted_on.isoformat()}')
        if vial.volume_ml and vial.volume_ml > 0:
            if dose_line is not None and concentration_mg_ml is not None:
                # Preserve BOTH physical volume and effective concentration
                # on the bounded label, using a single compact printed row.
                lines.append(
                    f'VOL:{_number(vial.volume_ml)}ML '
                    f'{_number(concentration_mg_ml)}MG/ML'
                )
            else:
                lines.append(f'VOL: {_number(vial.volume_ml)} ML')
                if concentration_mg_ml is not None:
                    lines.append(f'{_number(concentration_mg_ml)} MG/ML')
                else:
                    lines.append(
                        f'{_number(vial.content_value / vial.volume_ml)} '
                        f'{_plain(vial.content_unit)}/ML'
                    )
        else:
            lines.append('VOLUME NOT RECORDED')

        lines += [
            (
                f'BUD: {vial.beyond_use_on.isoformat()}'
                if vial.beyond_use_on
                else 'BUD NOT RECORDED'
            )
        ]
        if dose_line is not None:
            if (not isinstance(dose_line, str)
                    or not dose_line.startswith('TARGET:')
                    or len(dose_line) > 34
                    or not re.fullmatch(r'[A-Z0-9. :/\-]+', dose_line)):
                raise ValueError('Invalid target and U-100 label text')
            lines.append(dose_line)

    if vial.lot:
        lines.append('LOT: ' + _plain(vial.lot))

    if vial.cap_color:
        lines.append('CAP: ' + _plain(vial.cap_color))

    if vial.expires_on:
        lines.append('EXP: ' + vial.expires_on.isoformat())

    return [x for x in lines if x]


def _panel_size(layout):
    if layout not in LAYOUTS:
        raise ValueError('Unsupported label layout')

    mm_w, mm_h, cols, rows = LAYOUTS[layout]
    w, h = pixels(mm_w), pixels(mm_h)
    return w, h, cols, rows


def _selected(lines, width, height):
    max_chars = max(
        8,
        (width - 8) // (6 if width < 120 else 9),
    )
    max_rows = max(
        3,
        (height - 10) // (11 if width < 120 else 17),
    )

    # Reserve a printable row for target/markings ahead of optional metadata.
    # The legacy layout stays identical when no target has been selected.
    priority = (
        ('VIAL #', 'MIX:', 'BUD:', 'TARGET:', 'EXP:')
        if any(s.startswith('TARGET:') for s in lines)
        else ('MIX:', 'BUD:', 'VIAL #', 'EXP:')
    )

    ordered = (
        lines[:2]
        + [s for s in lines[2:] if s.startswith(priority)]
        + [s for s in lines[2:] if not s.startswith(priority)]
    )

    return [s[:max_chars] for s in ordered[:max_rows]]


def svg_bytes(lines, layout):
    w, h, cols, rows = _panel_size(layout)
    from .vial_label_compact758 import is_compact758, svg_panel758
    compact = is_compact758(lines, layout)
    width, height = w * cols, h * rows

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    for row in range(rows):
        for col in range(cols):
            x, y = col * w, row * h

            parts.append(
                f'<rect x="{x+1}" y="{y+1}" '
                f'width="{w-2}" height="{h-2}" '
                'fill="none" stroke="#555" stroke-width="1"/>'
            )

            if compact:
                parts.append(svg_panel758(lines, x, y, w, h, FONT))
                continue

            small = w < 120
            fontsize = 8 if small else 13
            step = 11 if small else 17

            for index, value in enumerate(_selected(lines, w, h)):
                safe = html.escape(value, quote=True)
                parts.append(
                    f'<text x="{x+4}" y="{y+step*(index+1)}" '
                    f'font-family="sans-serif" '
                    f'font-weight="bold" '
                    f'font-size="{fontsize}" '
                    f'fill="black">{safe}</text>'
                )

    parts.append('</svg>')
    return ''.join(parts).encode('utf-8')


# Built-in 5x7 bitmap font for PNG output without external dependencies.
FONT = {
'A':('01110','10001','10001','11111','10001','10001','10001'),
'B':('11110','10001','10001','11110','10001','10001','11110'),
'C':('01111','10000','10000','10000','10000','10000','01111'),
'D':('11110','10001','10001','10001','10001','10001','11110'),
'E':('11111','10000','10000','11110','10000','10000','11111'),
'F':('11111','10000','10000','11110','10000','10000','10000'),
'G':('01111','10000','10000','10111','10001','10001','01111'),
'H':('10001','10001','10001','11111','10001','10001','10001'),
'I':('11111','00100','00100','00100','00100','00100','11111'),
'J':('00111','00010','00010','00010','10010','10010','01100'),
'K':('10001','10010','10100','11000','10100','10010','10001'),
'L':('10000','10000','10000','10000','10000','10000','11111'),
'M':('10001','11011','10101','10101','10001','10001','10001'),
'N':('10001','11001','10101','10011','10001','10001','10001'),
'O':('01110','10001','10001','10001','10001','10001','01110'),
'P':('11110','10001','10001','11110','10000','10000','10000'),
'Q':('01110','10001','10001','10001','10101','10010','01101'),
'R':('11110','10001','10001','11110','10100','10010','10001'),
'S':('01111','10000','10000','01110','00001','00001','11110'),
'T':('11111','00100','00100','00100','00100','00100','00100'),
'U':('10001','10001','10001','10001','10001','10001','01110'),
'V':('10001','10001','10001','10001','10001','01010','00100'),
'W':('10001','10001','10001','10101','10101','10101','01010'),
'X':('10001','10001','01010','00100','01010','10001','10001'),
'Y':('10001','10001','01010','00100','00100','00100','00100'),
'Z':('11111','00001','00010','00100','01000','10000','11111'),
'0':('01110','10001','10011','10101','11001','10001','01110'),
'1':('00100','01100','00100','00100','00100','00100','01110'),
'2':('01110','10001','00001','00010','00100','01000','11111'),
'3':('11110','00001','00001','01110','00001','00001','11110'),
'4':('00010','00110','01010','10010','11111','00010','00010'),
'5':('11111','10000','10000','11110','00001','00001','11110'),
'6':('01111','10000','10000','11110','10001','10001','01110'),
'7':('11111','00001','00010','00100','01000','01000','01000'),
'8':('01110','10001','10001','01110','10001','10001','01110'),
'9':('01110','10001','10001','01111','00001','00001','11110'),
'#':('01010','11111','01010','01010','11111','01010','00000'),
':':('00000','00100','00100','00000','00100','00100','00000'),
'.':('00000','00000','00000','00000','00000','01100','01100'),
'/':('00001','00001','00010','00100','01000','10000','10000'),
'-':('00000','00000','00000','11111','00000','00000','00000'),
' ':('00000',)*7,
'=':('00000','11111','00000','11111','00000','00000','00000'),
'+':('00000','00100','00100','11111','00100','00100','00000'),
'(':('00010','00100','01000','01000','01000','00100','00010'),
')':('01000','00100','00010','00010','00010','00100','01000'),
'&':('01100','10010','10100','01000','10101','10010','01101'),
',':('00000','00000','00000','00000','00110','00100','01000'),
"'":('00100','00100','00010','00000','00000','00000','00000'),
# Explicit 5x7 lowercase glyphs used on the exact-format mg/mL and units
# lines. Legacy uppercase-only labels remain byte-identical.
'm':('00000','00000','11010','10101','10101','10101','00000'),
'g':('00000','01111','10001','10001','01111','00001','11110'),
'u':('00000','00000','10001','10001','10001','10011','01101'),
'n':('00000','00000','11110','10001','10001','10001','00000'),
'i':('00100','00000','01100','00100','00100','00100','01110'),
't':('00100','00100','11111','00100','00100','00101','00010'),
's':('00000','01111','10000','01110','00001','11110','00000'),
'?':('01110','10001','00001','00010','00100','00000','00100'),
}


def png_bytes(lines, layout):
    w, h, cols, rows = _panel_size(layout)
    from .vial_label_compact758 import is_compact758, geometry758
    compact = is_compact758(lines, layout)
    compact_dots = geometry758(lines, w, h, FONT) if compact else None
    width, height = w * cols, h * rows

    canvas = bytearray([255]) * (width * height)

    def point(x, y):
        if 0 <= x < width and 0 <= y < height:
            canvas[y * width + x] = 0

    for row in range(rows):
        for col in range(cols):
            bx, by = col * w, row * h

            for x in range(bx, bx + w):
                point(x, by)
                point(x, by + h - 1)

            for y in range(by, by + h):
                point(bx, y)
                point(bx + w - 1, y)

            if compact:
                for dx, dy in compact_dots:
                    point(bx + dx, by + dy)
                    point(bx + dx, by + dy + 1)
                continue

            scale = 1 if w < 120 else 2
            step = 11 if scale == 1 else 17
            # The new four-line layout needs compact horizontal glyphs
            # without shrinking the vertical 203-DPI bitmap text. Legacy
            # labels remain pixel-identical to their existing renderer.
            legacy_condensed = ((len(lines) == 4 and lines[-1].endswith(' units'))
                                or (len(lines) == 2 and ' / ' in lines[0]
                                    and ' / ' in lines[1]))
            scale_x = 1 if legacy_condensed else scale

            for index, line in enumerate(_selected(lines, w, h)):
                x0, y0 = bx + 4, by + 4 + index * step

                for j, ch in enumerate(line):
                    x = x0 + j * 6 * scale_x

                    if x + 5 * scale_x > bx + w - 3:
                        break

                    # Do not print '?' for the user's mg/mL/units text:
                    # lower-case bitmap glyphs use the readable capital
                    # equivalent where the legacy font has no lower-case.
                    for gy, bits in enumerate(FONT.get(ch, FONT.get(ch.upper(), FONT['?']))):
                        for gx, bit in enumerate(bits):
                            if bit == '1':
                                for sy in range(scale):
                                    for sx in range(scale_x):
                                        point(
                                            x + gx * scale_x + sx,
                                            y0 + gy * scale + sy,
                                        )

    def chunk(kind, data):
        return (
            struct.pack('>I', len(data))
            + kind
            + data
            + struct.pack(
                '>I',
                zlib.crc32(kind + data) & 0xffffffff,
            )
        )

    raw = b''.join(
        b'\0' + bytes(canvas[y * width:(y + 1) * width])
        for y in range(height)
    )

    ppm = round(DPI / 0.0254)

    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(
            b'IHDR',
            struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0),
        )
        + chunk(b'pHYs', struct.pack('>IIB', ppm, ppm, 1))
        + chunk(b'IDAT', zlib.compress(raw, 9))
        + chunk(b'IEND', b'')
    )
