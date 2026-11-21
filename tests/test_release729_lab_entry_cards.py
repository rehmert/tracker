"""Release 729: manual Labs mobile card markup and original form contract."""
from pathlib import Path
import re
from types import SimpleNamespace
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
FORM = ROOT / "app/templates/lab_form.html"
ROW = ROOT / "app/templates/_lab_row.html"
CSS = ROOT / "app/static/css/tracker-lab-navigation.css"
SHARED = ROOT / "app/static/css/tracker-mobile-ux673.css"


def test_729_one_manual_table_preserves_all_native_forms():
    src = FORM.read_text(encoding="utf-8")
    Environment().parse(src)
    assert src.count("ux673-card-table tracker-lab-result-cards729") == 1
    for token in ('id="lab-rows"', 'data-lab-manual-entry',
                  'data-lab-csv-entry', 'action="/labs/import-csv"',
                  'action="/labs"', 'hx-get="/labs/row"',
                  'hx-target="#lab-rows"',
                  'tracker-lab-navigation.css?v=729',
                  '<button class="primary">Save report</button>',
                  '<a class="btn" href="/labs">Cancel</a>'):
        assert src.count(token) == 1, token
    assert '{% include "_lab_row.html" %}' in src


def test_729_row_keeps_named_inputs_and_original_remove_behavior():
    src = ROW.read_text(encoding="utf-8")
    Environment().parse(src)
    assert src.count("<td ") == 6
    for name, label in (
        ("analyte", "Analyte"), ("value", "Value"), ("unit", "Unit"),
        ("ref_low", "Printed range, low"),
        ("ref_high", "Printed range, high"),
    ):
        assert src.count('data-label="' + label + '"') == 1
        assert src.count('name="' + name + '"') == 1
        assert src.count('aria-label="' + label + '"') == 1
    assert src.count('data-label="" data-ux673-action') == 1
    assert src.count('data-ux673-full') == 1
    assert "this.closest('tr').remove()" in src
    rendered = Environment().from_string(src).render(row=SimpleNamespace(
        analyte="TSH", value="1.25", unit="mIU/L",
        ref_low="0.4", ref_high="4.5",
    ))
    assert re.findall(r'name="([^"]+)"', rendered) == [
        "analyte", "value", "unit", "ref_low", "ref_high",
    ]
    assert 'value="1.25"' in rendered


def test_729_card_css_is_scoped_and_reuses_mobile_system():
    css = CSS.read_text(encoding="utf-8")
    shared = SHARED.read_text(encoding="utf-8")
    assert "@media screen and (max-width: 760px)" in css
    assert "table.tracker-lab-result-cards729 td input" in css
    assert "min-height: 44px" in css
    assert "font-size: 16px" in css
    assert "table.ux673-card-table" in shared
    assert "td[data-ux673-action]" in shared
    assert css.count("{") == css.count("}")
    assert css.count("/*") == css.count("*/")
