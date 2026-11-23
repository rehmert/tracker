"""Release 758 compact 30×15-mm text, identical glyph geometry in PNG and SVG.

A 203-DPI 5×7 font at two vertical pixels per dot has an effective cap
height around 5 pt (roughly a 6.5-pt nominal label-font setting). For
the unusually long first line, horizontal advance is condensed down to
five pixels, without overlapping or dropping any original characters.

This module has no external font, raster or UI dependencies.
"""
from __future__ import annotations

import html

COMPACT_LAYOUTS758 = frozenset(("30x15", "30x15x2"))


def is_compact758(lines, layout):
    """Recognize only the exact user-selected 2-/4-line vial formats."""
    return (layout in COMPACT_LAYOUTS758 and
            isinstance(lines, (list, tuple)) and
            len(lines) in (2, 4) and
            all(isinstance(s, str) for s in lines) and
            " / " in lines[0] and " / " in lines[1] and
            (len(lines) == 2 or lines[3].endswith(" units")))


def geometry758(lines, width, height, font):
    """Return 1x2 bitmap dots in sticker-local pixel coordinates.

    Geometry is deliberately shared by the PNG raster and SVG vector
    renderer. Any non-fitting input fails before either output is produced.
    """
    if len(lines) not in (2, 4) or any(not s for s in lines):
        raise ValueError("Expected exactly two or four nonempty vial label lines")
    if width < 230 or height < 110:
        raise ValueError("Compact vial text requires a physical 30x15 mm sticker")
    line_step = 21 if len(lines) == 4 else 30
    letter_height = 14   # 5x7 bitmap dots, 2 physical pixels per dot
    used_height = (len(lines) - 1) * line_step + letter_height
    first_y = (height - used_height) // 2
    if first_y < 4 or first_y + used_height > height - 4:
        raise ValueError("Complete compact label does not fit vertically")
    dots = []
    for row, line in enumerate(lines):
        # Every glyph is 5 px wide. Never overlap characters in order to
        # squeeze more text onto the label. No truncation, no font swapping.
        advance = min(6.0, (width - 8 - 5) / max(len(line) - 1, 1))
        if advance < 5.0:
            raise ValueError(
                "Label text is too long for 30x15 mm at the readable "
                "compact font size; abbreviate the compound or vendor."
            )
        y0 = first_y + row * line_step
        for j, ch in enumerate(line):
            glyph = font.get(ch)
            if glyph is None:
                raise ValueError(
                    f"Character {ch!r} cannot be printed faithfully "
                    "with the compact 30x15 label font."
                )
            x0 = 4 + round(j * advance)
            if x0 + 5 > width - 3:
                raise ValueError("Complete compact label exceeds sticker width")
            for gy, bits in enumerate(glyph):
                for gx, bit in enumerate(bits):
                    if bit == "1":
                        x, y = x0 + gx, y0 + gy * 2
                        dots.append((x, y))
    return dots


def svg_panel758(lines, x, y, width, height, font):
    """Accessible searchable text plus matching physically-rendered glyphs."""
    pixels = geometry758(lines, width, height, font)
    title = html.escape(" | ".join(lines), quote=True)
    paths = " ".join(
        f"M{x+px} {y+py}h1v2h-1z" for px, py in pixels
    )
    return (
        '<g class="tracker-compact-label758">'
        f"<title>{title}</title>"
        f'<path d="{paths}" fill="black"/>'
        "</g>"
    )
