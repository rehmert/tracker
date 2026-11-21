"""Release 727: Labs report rows become readable phone cards, same canonical table."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app/templates/labs.html"
MOBILE = ROOT / "app/static/css/tracker-mobile-ux673.css"
JS = ROOT / "app/static/js/tracker-labs-overview.js"


def report_table(reports):
    src = TPL.read_text(encoding="utf-8")
    start = src.index('<div class="scroll"><table class="ux673-card-table" id="labs-reports-table">')
    end = src.index("</table></div>", start) + len("</table></div>")
    env = Environment()
    env.filters["dt"] = lambda value: value.isoformat()
    return env.from_string(src[start:end]).render(reports=reports)


def test_727_single_labs_table_retains_report_filter_sort_and_empty_state():
    src = TPL.read_text(encoding="utf-8")
    Environment().parse(src)
    assert src.count('class="ux673-card-table" id="labs-reports-table"') == 1
    assert src.count('data-labs-report-row') == 1
    assert src.count('data-lab-report-date=') == 1
    assert src.count('data-lab-report-name=') == 1
    assert src.count('data-lab-report-results=') == 1
    for label in ("Drawn", "Lab", "Results", "File"):
        assert src.count('data-label="' + label + '"') == 1
        assert 'scope="col">' + label + '</th>' in src or (
            label == "Results" and 'scope="col" class="n">Results</th>' in src
        )
    empty = report_table([])
    assert "No lab reports yet." in empty
    assert empty.count('colspan="4"') == 1
    assert "data-labs-report-row" not in empty
    row = SimpleNamespace(id=987, drawn_on=date(2026,11,20),
                          lab_name="Example Lab", stored_name="example.pdf",
                          results=[1,2,3])
    rendered = report_table([row])
    assert rendered.count("data-labs-report-row") == 1
    assert 'href="/labs/987"' in rendered
    assert 'data-lab-report-date="2026-11-20"' in rendered
    assert 'data-lab-report-name="Example Lab"' in rendered
    assert 'data-lab-report-results="3"' in rendered
    assert "Example Lab" in rendered


def test_727_reuses_mobile_card_system_without_new_data_mutations():
    css = MOBILE.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    assert "#main-content table.ux673-card-table" in css
    assert 'tr[hidden] { display: none !important; }' in css
    assert "td::before" in css and "attr(data-label)" in css
    assert "data-ux673-action" in css
    assert "row.hidden = !show" in js
    assert "reportTable.querySelectorAll('tbody [data-labs-report-row]')" in js
    assert "localStorage" not in js
    assert "fetch(" not in js
