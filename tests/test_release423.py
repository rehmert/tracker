"""Release 423: labels, scoped routes, macros, and weight defaults."""

import struct
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi.routing import APIRoute

from app.routers import vials
from app.scoped_db390 import get_scoped_db390
from app.vial_labels423 import (
    LAYOUTS,
    label_lines,
    png_bytes,
    svg_bytes,
    pixels,
)


def vial(**kwargs):
    data = dict(
        id=42,
        compound=SimpleNamespace(name='Sample <Peptide>'),
        content_value=10,
        content_unit='mg',
        label='TEST-01',
        lot='A&1',
        cap_color='blue',
        reconstituted_on=None,
        volume_ml=None,
        beyond_use_on=None,
        expires_on=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_png_is_true_203dpi_and_expected_shape():
    for layout in LAYOUTS:
        w, h, cols, rows = LAYOUTS[layout]
        png = png_bytes(label_lines(vial(), 'pre'), layout)

        assert png.startswith(b'\x89PNG\r\n\x1a\n')

        width, height = struct.unpack('>II', png[16:24])
        assert (width, height) == (
            pixels(w) * cols,
            pixels(h) * rows,
        )

        assert b'pHYs' in png

        start = png.index(b'pHYs') + 4
        assert struct.unpack('>II', png[start:start+8]) == (
            7992, 7992
        )


def test_escaped_svg_and_no_invented_expiry():
    lines = label_lines(vial(), 'pre')

    assert not any(
        'EXP:' in x or 'BUD:' in x
        for x in lines
    )

    svg = svg_bytes(lines, '40x20').decode()

    assert 'SAMPLE &lt;PEPTIDE&gt;' in svg
    assert '&amp;' in svg
    assert '<svg' in svg


def test_mixed_label_needs_recorded_reconstitution():
    import pytest

    with pytest.raises(ValueError, match='reconstitution'):
        label_lines(vial(), 'post')

    v = vial(
        reconstituted_on=date(2026, 11, 5),
        volume_ml=2,
        beyond_use_on=date(2026, 11, 15),
    )

    lines = label_lines(v, 'post')

    assert 'MIX: 2026-11-05' in lines
    assert '5 MG/ML' in lines
    assert 'BUD: 2026-11-15' in lines


def test_both_routes_remain_database_scoped():
    paths = {
        route.path: route
        for route in vials.router.routes
        if isinstance(route, APIRoute)
    }

    for path in (
        '/vials/{vid}/labels',
        '/vials/{vid}/labels/export',
    ):
        assert path in paths
        dependencies = {
            item.call
            for item in paths[path].dependant.dependencies
        }
        assert get_scoped_db390 in dependencies


def test_macro_ui_preserves_partial_data_and_weight_units():
    base = Path(__file__).resolve().parents[1]
    html = (base / 'app/templates/food.html').read_text()

    assert 'food423-macros' in html
    assert 'coverage[key] == food_count' in html
    assert 'Comparison unavailable: incomplete food data' in html
    assert 'target-consumed' in html

    vitals = (base / 'app/routers/vitals.py').read_text()

    assert (
        vitals.count(
            'weight_unit: str = Form(config.WEIGHT_UNIT)'
        ) == 2
    )

    from app import config, metrics

    assert config.WEIGHT_UNIT in ('lb', 'kg')
    assert abs(metrics.weight_to_kg(220, 'lb') - 99.7903) < .02
