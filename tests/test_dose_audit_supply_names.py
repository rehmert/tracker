"""Dose audit uses readable names while preserving original supply IDs."""

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


def test_lookup_is_scoped_to_edit_route():
    source = ROUTER.read_text()

    start = source.index('@router.get("/doses/{did}/edit")')
    end = source.index(
        '@router.post("/doses/{did}/edit")',
        start,
    )

    edit = source[start:end]

    assert (
        "supplies = list(db.scalars("
        "select(Supply).order_by(Supply.name)))"
        in edit
    )
    assert (
        "supply_names = {str(s.id): s.name for s in supplies}"
        in edit
    )
    assert "supplies=supplies" in edit
    assert "supply_names=supply_names" in edit


def test_before_and_after_show_readable_names():
    fragment = audit_fragment()

    assert fragment.count(
        'class="dose-audit-supply-list"'
    ) == 2

    assert "before.get('supplies', {}).items()" in fragment
    assert "after.get('supplies', {}).items()" in fragment

    assert fragment.count(
        "(supply_names|default({})).get("
    ) == 2

    assert fragment.count(
        "<small>(ID {{ supply_id }})</small>"
    ) == 2

    assert "before.get('supplies', {}) | tojson" in fragment
    assert "after.get('supplies', {}) | tojson" in fragment


def test_existing_and_deleted_supplies():
    template = Environment(autoescape=True).from_string(
        audit_fragment()
    )

    rendered = template.render(
        before={"supplies": {"15": 1, "99": 2}},
        after={"supplies": {"15": 3}},
        supply_names={"15": "BD 1 mL Syringe"},
    )

    assert "BD 1 mL Syringe" in rendered
    assert "Supply #99" in rendered
    assert "ID 15" in rendered
    assert "ID 99" in rendered
    assert '"15": 1' in rendered
    assert '"15": 3' in rendered
    assert '"99": 2' in rendered


def test_empty_historical_snapshot():
    template = Environment(autoescape=True).from_string(
        audit_fragment()
    )

    rendered = template.render(before={}, after={})

    assert rendered.count("None recorded") == 2
    assert rendered.count("{}") >= 2


def test_html_in_supply_names_is_escaped():
    template = Environment(autoescape=True).from_string(
        audit_fragment()
    )

    rendered = template.render(
        before={"supplies": {"1": 1}},
        after={"supplies": {"1": 2}},
        supply_names={"1": "<script>alert(1)</script>"},
    )

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_existing_audit_and_inventory_protections():
    html = HTML.read_text()
    router = ROUTER.read_text()

    assert html.count(
        '<section class="card wide" aria-label="Change history">'
    ) == 1
    assert 'action="/doses/{{ dose.id }}/edit"' in html

    assert "_dose_snapshot(d, old_usage)" in router
    assert "manual_supplies.selections(" in router
    assert "reserve_inventory_write" in router
    assert 'action="edit"' in router

    Environment().parse(html)
