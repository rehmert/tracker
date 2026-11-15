"""Global, presentation-only heading capitalization."""

from pathlib import Path

from app.templating import templates


ROOT = Path(__file__).resolve().parents[1]


def test_global_script_registered():
    base = (
        ROOT / "app/templates/base.html"
    ).read_text()

    assert base.count(
        "tracker-page-title-case.js"
    ) == 1


def test_page_title_case_uses_safe_scope():
    js = (
        ROOT /
        "app/static/js/tracker-page-title-case.js"
    ).read_text()

    assert "main-content" in js
    assert "document.title" in js
    assert "NodeFilter.SHOW_TEXT" in js
    assert "MutationObserver" in js
    assert "htmx:afterSwap" in js
    assert "data-no-title-case" in js


def test_technical_terms_are_preserved():
    js = (
        ROOT /
        "app/static/js/tracker-page-title-case.js"
    ).read_text()

    for term in (
        "PK", "FEFO", "SQLite",
        "COAs", "CSV", "HTMX"
    ):
        assert f'"{term}"' in js


def test_base_template_parses():
    templates.env.get_template("base.html")


def test_notes_title_preserves_scientific_looking_identifiers():
    """Notes headings must not turn UUID-like substrings into an em dash.

    The number formatter treats 244e49381732 as overflowing scientific
    notation unless the user-authored title is expressly excluded.
    """
    from app.templating import templates

    number_js = (ROOT / "app/static/js/tracker-number-display563.js").read_text()
    template = (ROOT / "app/templates/page_view.html").read_text()
    assert "[data-preserve-numbers]" in number_js
    assert '<h1 data-no-title-case data-preserve-numbers>{{ p.title }}</h1>' in template
    # The title-case formatter also excludes this same user-authored heading.
    title_js = (ROOT / "app/static/js/tracker-page-title-case.js").read_text()
    assert "[data-no-title-case]" in title_js
    templates.env.get_template("page_view.html")


def test_635_targeted_notes_browser_gate_is_exact_and_disposable():
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    assert '"$TARGETED_MODULE" == note-title575' in runner
    assert 'TARGETED_NOTES_575_SCOPE=HTTP_AND_HTTPS_ONLY' in runner
    assert 'tests/browser/test_strict_csrf521.py::test_575_create_and_edit_notes_with_rendered_dynamic_action' in runner
    start = runner.index('if [[ "$MODE" == targeted && "$TARGETED_MODULE" == note-title575 ]]')
    end = runner.index('if [[ "$MODE" == full ]]; then', start)
    gate = runner[start:end]
    assert 'TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1' in gate
    assert 'TRACKER_BROWSER_QA_DATA_DIR="$DATA"' in gate
    assert 'exit 0' in gate
    assert 'tests/browser/test_strict_csrf521.py\n' not in gate
