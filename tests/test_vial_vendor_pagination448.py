"""Release 448: purchase vendor and paginated vial list integration contracts.

No permanent users, migrations, or live database writes are required.
"""
import ast
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

from app.models import Purchase, Vial
from app.routers import vials

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
SORT = ROOT / "app/static/js/tracker-vials-sort.js"
PAGES = ROOT / "app/static/js/tracker-vial-pages448.js"
SELECT = ROOT / "app/static/js/tracker-bulk-selection.js"
ATTENTION = ROOT / "app/static/js/tracker-attention-navigation.js"
STYLE = ROOT / "app/static/css/tracker-vial-pages448.css"


def test_vendor_is_sourced_from_vials_purchase_without_schema_changes():
    assert hasattr(Vial, "purchase")
    assert hasattr(Vial, "purchase_id")
    assert hasattr(Purchase, "vendor")
    assert "selectinload(Vial.purchase)" in (
        ROOT / "app/routers/vials.py"
    ).read_text()
    assert "vendor" not in Vial.__table__.columns
    assert "vendor" in Purchase.__table__.columns


def test_vials_listing_retains_all_filtered_rows_and_eager_loads_vendor(monkeypatch):
    fake_vials = [
        SimpleNamespace(id=11, purchase=SimpleNamespace(vendor="Example A")),
        SimpleNamespace(id=12, purchase=None),
    ]
    query_log = []

    class DB:
        def scalars(self, query):
            query_log.append(query)
            return iter(fake_vials if len(query_log) == 1 else [])

    observed = {}
    monkeypatch.setattr(
        vials.services, "vial_views", lambda db, items: {x.id: object() for x in items}
    )

    def record(request, template, **context):
        observed.update(context)
        observed["template"] = template
        return observed

    monkeypatch.setattr(vials, "render", record)
    result = vials.vials_page(
        request=object(), status="active", compound_id=None, db=DB()
    )
    assert result["template"] == "vials.html"
    assert result["vials"] == fake_vials
    assert len(query_log) == 2
    assert query_log[0]._with_options, (
        "Expected eager purchase loading on the vial listing"
    )
    assert result["status"] == "active"


@pytest.mark.parametrize(
    "vendor,expected",
    [
        ("Northstar Labs", "Northstar Labs"),
        ("", "—"),
        (None, "—"),
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
    ],
)
def test_vendor_template_escapes_data_and_handles_missing_values(vendor, expected):
    html = TEMPLATE.read_text()
    expression = "{{ v.purchase.vendor if v.purchase and v.purchase.vendor else '—' }}"
    assert expression in html
    rendered = Environment(autoescape=True).from_string(expression).render(
        v=SimpleNamespace(
            purchase=SimpleNamespace(vendor=vendor)
        )
    )
    assert rendered == expected
    no_purchase = Environment(autoescape=True).from_string(expression).render(
        v=SimpleNamespace(purchase=None)
    )
    assert no_purchase == "—"


def test_vendor_column_follows_status_to_keep_legacy_column_indices():
    source = TEMPLATE.read_text()
    assert 'data-vial-sort="vendor"' in source
    assert "<button type=\"button\" class=\"vial-sort-button\">Vendor</button>" in source
    assert source.index('data-vial-sort="status"') < source.index(
        'data-vial-sort="vendor"'
    )
    assert '<td colspan="10" class="empty">' in source
    sort = SORT.read_text()
    for key, index in {
        "compound": 1, "vial": 2, "remaining": 3,
        "amount": 4, "landed": 5, "cost": 6,
        "coa": 7, "status": 8, "vendor": 9,
    }.items():
        assert f"{key}: {index}" in sort
    assert "tracker:vials-sorted" in sort


def test_pager_ui_has_mobile_controls_and_nonjavascript_fallback():
    source = TEMPLATE.read_text()
    for control in (
        "tracker-vial-pager448",
        "tracker-vial-page-size448",
        "tracker-vial-first448",
        "tracker-vial-prev448",
        "tracker-vial-page-info448",
        "tracker-vial-next448",
        "tracker-vial-last448",
    ):
        assert f'id="{control}"' in source
    for value in ("25", "50", "100", "0"):
        assert f'<option value="{value}">' in source
    assert 'class="card" aria-label="Vial table pages" hidden>' in source
    assert "tracker-vial-pages448.js?v=448" in source
    assert "tracker-vial-pages448.css?v=448" in source
    css = STYLE.read_text()
    assert "tbody tr[hidden]" in css
    assert "display: none !important" in css
    assert "@media (max-width: 680px)" in css


def test_client_pager_keeps_rows_for_filters_reports_and_cross_page_sorting():
    source = PAGES.read_text()
    assert 'table.tBodies[0].rows' in source
    assert 'row.querySelector("input.bulk-vial-check")' in source
    assert "row.hidden = index < start || index >= end" in source
    assert "tracker:vials-sorted" in source
    assert "page = 0" in source
    assert "tracker:vials-page-changed" in source
    assert "sessionStorage" in source
    assert "fetch(" not in source
    assert ".remove()" not in source
    assert ".delete(" not in source


def test_selection_persists_and_select_all_only_operates_on_current_page():
    source = SELECT.read_text()
    assert "pageBoxes = () => boxes.filter(" in source
    assert "tracker:vials-page-changed" in source
    assert "'bulk-select-all':()=>{for(const b of pageBoxes())" in source
    assert "'bulk7-clear':()=>{for(const b of pageBoxes())" in source
    assert "for(const b of pageBoxes())b.checked=all.checked" in source
    assert 'tracker.bulkVials.selection.v1' in source
    assert "input.type='hidden'; input.name='vial_ids'" in source
    # Unhidden rows remain selected across navigation; no page event clears selection.
    source_pages = PAGES.read_text()
    assert "tracker.bulkVials.selection.v1" not in source_pages
    assert "selected = {}" not in source_pages


def test_quick_find_and_attention_navigation_reveal_other_pages():
    source = TEMPLATE.read_text()
    nav = ATTENTION.read_text()
    pager = PAGES.read_text()
    assert "tracker:vials-show-row" in source
    assert "tracker:vials-show-row" in nav
    assert 'document.addEventListener("tracker:vials-show-row"' in pager
    assert "rows.indexOf(row)" in pager
    assert "Math.floor(index / size)" in pager


def test_existing_detailed_csv_and_attention_logic_remain_on_same_columns():
    for name, snippets in (
        ("app/static/js/tracker-vial-attention.js", ["row.cells[2]"]),
        (
            "app/static/js/tracker-inventory-review-tools.js",
            ["cells[1]", "cells[2]", "cells[4]", "cells[7]"],
        ),
    ):
        source = (ROOT / name).read_text()
        for snippet in snippets:
            assert snippet in source


def test_unchanged_route_scoping_and_no_new_write_endpoint():
    source = (ROOT / "app/routers/vials.py").read_text()
    tree = ast.parse(source)
    scoped = [
        call for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "Depends"
        and call.args
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "get_scoped_db390"
    ]
    assert len(scoped) == 18
    tests = (ROOT / "tests/test_core_user_db394.py").read_text()
    assert '"vials": 18' in tests
    assert "sum(CORE.values()) == 56" in tests
    assert 'get_scoped_db390' in source


@pytest.mark.parametrize(
    "filename",
    [
        "app/static/js/tracker-vial-pages448.js",
        "app/static/js/tracker-vials-sort.js",
        "app/static/js/tracker-bulk-selection.js",
        "app/static/js/tracker-attention-navigation.js",
    ],
)
def test_javascript_parses_with_node_when_available(filename):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not available to syntax-check browser JavaScript")
    result = subprocess.run(
        [node, "--check", str(ROOT / filename)],
        capture_output=True, text=True, check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_pagination_behavior_in_isolated_javascript_runtime_when_node_exists():
    """Exercise real pager JS with 60 mocked DOM rows: no browser package needed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not available for runtime pagination acceptance")

    program = r"""
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const handlers = {};
function control() {
  const listeners = {};
  return {
    hidden: true, disabled: false, value: "25", textContent: "",
    addEventListener(name, fn) {listeners[name] = fn;},
    click() {listeners.click?.();},
    change() {listeners.change?.();}
  };
}
const rows = Array.from({length: 60}, (_, i) => ({
  id: i + 1,
  hidden: false,
  querySelector(name) {
    return name === "input.bulk-vial-check" ? {value: String(i + 1)} : null;
  }
}));
const table = {tBodies: [{rows}]};
const ids = {};
for (const name of [
  "tracker-vial-pager448", "tracker-vial-page-size448",
  "tracker-vial-page-info448", "tracker-vial-first448",
  "tracker-vial-prev448", "tracker-vial-next448",
  "tracker-vial-last448"
]) ids[name] = control();
ids["tracker-vials-sortable"] = table;
const document = {
  readyState: "complete",
  getElementById(name) {return ids[name] || null;},
  addEventListener(name, fn) {handlers[name] = fn;},
  dispatchEvent(event) {handlers[event.type]?.(event);}
};
const stored = new Map();
const sessionStorage = {
  getItem(key) {return stored.has(key) ? stored.get(key) : null;},
  setItem(key, value) {stored.set(key, value);}
};
vm.runInNewContext(
  fs.readFileSync(process.argv[1], "utf8"),
  {document, sessionStorage, Event: function(type){this.type=type;}}
);
const visible = () => rows.filter(row => !row.hidden).map(row => row.id);
assert.equal(visible().length, 25);
assert.deepEqual(visible(), Array.from({length:25},(_,i)=>i+1));
ids["tracker-vial-next448"].click();
assert.equal(visible().length, 25);
assert.equal(visible()[0], 26);
ids["tracker-vial-next448"].click();
assert.equal(visible().length, 10);
assert.equal(visible()[0], 51);
assert(ids["tracker-vial-next448"].disabled);
document.dispatchEvent({type:"tracker:vials-show-row",detail:{row:rows[3]}});
assert.equal(visible()[0], 1);
assert(visible().includes(4));
rows.reverse();
document.dispatchEvent({type:"tracker:vials-sorted"});
assert.equal(visible()[0], 60);
assert.equal(visible().length, 25);
ids["tracker-vial-page-size448"].value = "0";
ids["tracker-vial-page-size448"].change();
assert.equal(visible().length, 60);
assert.equal(stored.get("tracker.vials.pageSize448"), "0");
ids["tracker-vial-page-size448"].value = "50";
ids["tracker-vial-page-size448"].change();
assert.equal(visible().length, 50);
ids["tracker-vial-last448"].click();
assert.equal(visible().length, 10);
assert.equal(visible()[0], 10);
assert(!ids["tracker-vial-pager448"].hidden);
assert(ids["tracker-vial-page-info448"].textContent.includes("of 60"));
console.log("PASS: 60-row pagination, sorting, reveal, page sizes and controls");
"""
    result = subprocess.run(
        [node, "-e", program, str(PAGES)],
        capture_output=True, text=True, check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: 60-row pagination" in result.stdout
