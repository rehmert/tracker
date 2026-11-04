"""Dose correction audit details render stored snapshots safely."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def audit_fragment():
    source = HTML.read_text()
    start_tag = '<details class="dose-audit-details">'
    assert source.count(start_tag) == 1

    start = source.index(start_tag)
    end = source.index("</details>", start) + len("</details>")

    return source[start:end]


def test_edit_page_and_existing_history_preserved():
    source = HTML.read_text()

    assert source.startswith(
        '{% extends "base.html" %}'
        '{% block title %}Edit dose{% endblock %}'
        '{% block content %}'
    )
    assert source.count(
        '<section class="card wide" aria-label="Change history">'
    ) == 1

    assert source.count('{% for event in history %}') == 1
    assert source.count('class="dose-audit-details"') == 1
    assert 'event.before_json | from_json' in source
    assert 'event.after_json | from_json' in source

    Environment().parse(source)


def test_full_snapshots_are_displayed():
    fragment = audit_fragment()

    for field in (
        "vial_id",
        "taken_at",
        "entered_value",
        "entered_unit",
        "amount_base",
        "kind",
        "site",
        "notes",
        "supplies",
    ):
        assert f"before.get('{field}'" in fragment
        assert f"after.get('{field}'" in fragment

    assert "View recorded changes" in fragment
    assert "Supply IDs and quantities" in fragment


def test_render_escapes_untrusted_notes_and_supplies():
    fragment = audit_fragment()
    template = Environment(autoescape=True).from_string(fragment)

    html = template.render(
        before={
            "vial_id": 1,
            "taken_at": "2026-11-01T08:00:00",
            "entered_value": 2,
            "entered_unit": "mg",
            "amount_base": 2000,
            "kind": "dose",
            "site": "Abdomen",
            "notes": "<script>alert(1)</script>",
            "supplies": {"15": 1},
        },
        after={
            "vial_id": 1,
            "taken_at": "2026-11-01T08:05:00",
            "entered_value": 2.5,
            "entered_unit": "mg",
            "amount_base": 2500,
            "kind": "dose",
            "site": "Quadriceps",
            "notes": "Corrected timestamp",
            "supplies": {"15": 2},
        },
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "2026-11-01T08:05:00" in html
    assert "Corrected timestamp" in html
    assert '"15": 1' in html
    assert '"15": 2' in html


def test_empty_snapshot_is_displayable():
    fragment = audit_fragment()
    html = Environment(autoescape=True).from_string(
        fragment
    ).render(before={}, after={})

    assert "View recorded changes" in html
    assert "—" in html
    assert "{}" in html


def test_audit_and_inventory_backend_unchanged():
    router = ROUTER.read_text()

    assert "_dose_snapshot(d, old_usage)" in router
    assert 'before_json=json.dumps(before)' in router
    assert 'after_json=json.dumps(after)' in router
    assert 'action="edit"' in router
    assert "reserve_inventory_write" in router
    assert "manual_supplies.selections(" in router
