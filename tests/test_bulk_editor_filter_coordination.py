"""Search, edited-only filtering and bulk-edit shortcuts cooperate."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
FINDER = ROOT / "app/static/js/tracker-bulk-field-finder.js"
GUIDED = ROOT / "app/static/js/tracker-bulk-editor-guided.js"
HTML = ROOT / "app/templates/vials.html"
ROUTER = ROOT / "app/routers/vials.py"


def visible(query_matches, edited, edited_only):
    """Independent reference for composed field visibility."""
    return (query_matches or edited) and (
        not edited_only or edited
    )


def test_normal_search_retains_requested_edits():
    assert visible(False, True, False)
    assert visible(True, False, False)
    assert not visible(False, False, False)


def test_edited_only_hides_unchanged_fields():
    assert not visible(True, False, True)
    assert visible(False, True, True)
    assert visible(True, True, True)


def test_empty_search_and_edited_only():
    # Empty query treats all fields as matching.
    assert visible(True, True, True)
    assert not visible(True, False, True)
    assert visible(True, False, False)


def test_finder_combines_both_filters():
    source = FINDER.read_text()

    for marker in (
        'document.getElementById("bulk-show-edited-only")',
        "const visible = matches || changed;",
        "const permitted = !editsOnly?.checked || changed;",
        "field.hidden = !(visible && permitted);",
        "group.hidden = visibleFields.length === 0;",
        'editsOnly?.addEventListener("change", refresh);',
        'form.addEventListener("input", event => {',
        'form.addEventListener("change", event => {',
        "modeNote",
        "Showing requested changes only",
    ):
        assert marker in source, marker


def test_quick_edit_reveals_target_before_focus():
    source = GUIDED.read_text()

    required = (
        'const fieldSearch = document.getElementById("bulk-field-search");',
        'fieldSearch.value = "";',
        'new Event("input", {bubbles:true})',
        'const target = fields.find(field => field.dataset.bulkField === key);',
        "if (group) group.open = true;",
        "target.scrollIntoView(",
    )

    for marker in required:
        assert marker in source, marker

    assert (
        source.index('fieldSearch.value = "";')
        < source.index(
            'const target = fields.find(field => field.dataset.bulkField === key);'
        )
    )


def test_scripts_are_read_only():
    finder = FINDER.read_text()
    guided = GUIDED.read_text()

    for source in (finder, guided):
        assert "fetch(" not in source
        assert "requestSubmit(" not in source
        assert "form.submit(" not in source


def test_template_and_backend_contracts():
    html = HTML.read_text()
    backend = ROUTER.read_text()

    assert "tracker-bulk-field-finder.js?v=20261104-b37" in html
    assert "tracker-bulk-editor-guided.js?v=20261104-b37" in html
    assert 'id="bulk-field-search"' in html
    assert 'id="bulk-show-edited-only"' in html
    assert 'id="bulk-edit-field-groups"' in html
    assert "def _bulk_validate(" in backend
    assert "def _bulk_snapshot(" in backend
    assert '"/vials/bulk/preview"' in backend

    Environment().parse(html)
