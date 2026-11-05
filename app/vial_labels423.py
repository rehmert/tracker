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


def label_lines(vial, phase):
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
        lines += [
            f'MIX: {vial.reconstituted_on.isoformat()}',
            (
                f'VOL: {_number(vial.volume_ml)} ML'
                if vial.volume_ml
                else 'VOLUME NOT RECORDED'
            ),
        ]

        if vial.volume_ml and vial.volume_ml > 0:
            lines += [
                f'{_number(vial.content_value / vial.volume_ml)} '
                f'{_plain(vial.content_unit)}/ML'
            ]

        lines += [
            (
                f'BUD: {vial.beyond_use_on.isoformat()}'
                if vial.beyond_use_on
                else 'BUD NOT RECORDED'
            )
        ]

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

    priority = ('MIX:', 'BUD:', 'VIAL #', 'EXP:')

    ordered = (
        lines[:2]
        + [s for s in lines[2:] if s.startswith(priority)]
        + [s for s in lines[2:] if not s.startswith(priority)]
    )

    return [s[:max_chars] for s in ordered[:max_rows]]


def svg_bytes(lines, layout):
    w, h, cols, rows = _panel_size(layout)
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
'?':('01110','10001','00001','00010','00100','00000','00100'),
}


def png_bytes(lines, layout):
    w, h, cols, rows = _panel_size(layout)
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

            scale = 1 if w < 120 else 2
            step = 11 if scale == 1 else 17

            for index, line in enumerate(_selected(lines, w, h)):
                x0, y0 = bx + 4, by + 4 + index * step

                for j, ch in enumerate(line):
                    x = x0 + j * 6 * scale

                    if x + 5 * scale > bx + w - 3:
                        break

                    for gy, bits in enumerate(FONT.get(ch, FONT['?'])):
                        for gx, bit in enumerate(bits):
                            if bit == '1':
                                for sy in range(scale):
                                    for sx in range(scale):
                                        point(
                                            x + gx * scale + sx,
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
