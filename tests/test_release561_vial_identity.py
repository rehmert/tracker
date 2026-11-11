"""Release 561: unambiguous vial identity in inventory and blends."""

from pathlib import Path

from jinja2 import Environment, DictLoader

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_table_shows_unique_id_and_metadata():
    source = (
        ROOT / "app/templates/vials.html"
    ).read_text()

    assert (
        'href="/vials/{{ v.id }}">#{{ v.id }}'
    ) in source

    assert "· {{ v.label }}" in source
    assert "Lot: {{ v.lot }}" in source
    assert "Select vial #{{ v.id }}" in source


def test_blend_source_option_keeps_original_id_value():
    source = (
        ROOT / "app/templates/blends.html"
    ).read_text()

    assert (
        '<option value="{{ v.id }}"'
    ) in source

    assert '>#{{ v.id }} · {{ {"tirzepatide":"Tirz"' in source

    assert "{{ v.purchase.vendor if v.purchase and v.purchase.vendor else \"—\" }}" in source
    assert "{{ v.lot or \"—\" }}" in source
    assert "{{ d.remaining_base|amt(d.dim) }}" in source
    assert "{{ d.remaining_base|amt(d.dim) }} remaining" not in source


def test_both_templates_parse():
    env = Environment()

    for filename in (
        "app/templates/vials.html",
        "app/templates/blends.html",
    ):
        env.parse((ROOT / filename).read_text())


def test_identity_fields_render_for_duplicate_labels():
    source = (
        ROOT / "app/templates/blends.html"
    ).read_text()

    from types import SimpleNamespace as NS

    # Render the actual option fragment independently from the
    # broader template's unrelated page context.
    start = source.index(
        '<option value="{{ v.id }}" data-unit='
    )

    stop = source.index(
        "</option>", start
    ) + len("</option>")

    fragment = source[start:stop]

    env = Environment()
    env.filters["amt"] = (
        lambda value, dim: f"{value:g} mg"
    )

    template = env.from_string(fragment)

    compound = NS(name="Tirzepatide")

    def render(vid):
        vial = NS(
            id=vid,
            label="30 mg",
            lot="TZ-0926",
            compound=compound,
            purchase=NS(vendor="APM"),
            content_unit="mg",
            volume_ml=None,
        )

        return template.render(
            v=vial,
            d=NS(
                remaining_base=30,
                dim="mass",
            ),
            amt=lambda value, dim: f"{value:g} mg",
        )

    first = render(142)
    second = render(143)

    assert '#142 · Tirz · APM · TZ-0926 · 30 mg' in first
    assert '#143 · Tirz · APM · TZ-0926 · 30 mg' in second

    assert 'value="142"' in first
    assert 'value="143"' in second

    assert first != second
