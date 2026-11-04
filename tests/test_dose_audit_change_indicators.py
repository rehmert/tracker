"""Highlight changed fields in existing dose audit snapshots."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def audit_fragment():
    source = HTML.read_text()
    marker = '<details class="dose-audit-details">'

    assert source.count(marker) == 1

    start = source.index(marker)
    end = source.index("</details>", start) + len("</details>")

    return source[start:end]


def test_all_eight_fields_have_change_indicators():
    source = audit_fragment()

    assert "<th>Change</th>" in source
    assert source.count(
        'class="dose-audit-change-status"'
    ) == 8
    assert source.count(
        "<strong>Changed</strong>"
    ) == 8

    labels = (
        "Vial ID",
        "Recorded time",
        "Entered amount",
        "Counted amount (base unit)",
        "Entry type",
        "Injection site",
        "Notes",
        "Supply IDs and quantities",
    )

    for label in labels:
        assert f'<th scope="row">{label}</th>' in source


def test_entered_amount_compares_value_and_unit():
    source = audit_fragment()

    assert (
        "before.get('entered_value') != after.get('entered_value')"
        in source
    )
    assert (
        "before.get('entered_unit') != after.get('entered_unit')"
        in source
    )


def test_only_changed_fields_are_highlighted():
    template = Environment(autoescape=True).from_string(
        audit_fragment()
    )

    original = {
        "vial_id": 8,
        "taken_at": "2026-11-03T08:00:00",
        "entered_value": 2,
        "entered_unit": "mg",
        "amount_base": 2000,
        "kind": "dose",
        "site": "Abdomen",
        "notes": "Recorded",
        "supplies": {"15": 1},
    }

    corrected = dict(original)
    corrected["taken_at"] = "2026-11-03T08:15:00"
    corrected["site"] = "Quadriceps"
    corrected["notes"] = "Time corrected"

    rendered = template.render(
        before=original,
        after=corrected,
        supply_names={"15": "Syringe"},
    )

    assert rendered.count("<strong>Changed</strong>") == 3
    assert rendered.count(">Unchanged") == 5

    assert "2026-11-03T08:15:00" in rendered
    assert "Time corrected" in rendered


def test_empty_snapshots_render():
    template = Environment(autoescape=True).from_string(
        audit_fragment()
    )

    rendered = template.render(before={}, after={})

    assert "<strong>Changed</strong>" not in rendered
    assert rendered.count(">Unchanged") == 8


def test_supply_names_and_original_json_preserved():
    fragment = audit_fragment()
    html = HTML.read_text()

    assert "before.get('supplies', {}) | tojson" in fragment
    assert "after.get('supplies', {}) | tojson" in fragment
    assert "supply_names|default({})" in fragment

    assert html.count(
        '<section class="card wide" aria-label="Change history">'
    ) == 1
    assert 'action="/doses/{{ dose.id }}/edit"' in html

    Environment().parse(html)


def test_template_contains_no_trailing_whitespace():
    for number, line in enumerate(
        HTML.read_text().splitlines(), 1
    ):
        assert line == line.rstrip(), number


def test_backend_recording_is_unchanged():
    router = ROUTER.read_text()

    assert "_dose_snapshot(d, old_usage)" in router
    assert "manual_supplies.selections(" in router
    assert "reserve_inventory_write" in router
    assert 'action="edit"' in router
