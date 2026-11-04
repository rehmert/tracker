"""Vial quick-find batching and keyboard safety contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
MANAGER = ROOT / "app/static/js/tracker-bulk-selection.js"


def quick_find_script():
    source = TEMPLATE.read_text()
    marker = "/* STAGE34_VIAL_QUICK_FIND_JS */"
    start = source.index(marker)
    end = source.index("</script>", start)
    return source[start:end]


def test_select_matching_uses_one_notification():
    source = quick_find_script()

    assert "unchecked.forEach(" in source or (
        "for (const checkbox of unchecked)" in source
    )
    assert "checkbox.checked = true;" in source
    assert source.count("unchecked[0].dispatchEvent(") == 1
    assert "checkbox.dispatchEvent(" not in source


def test_cross_view_selection_limit_remains():
    source = MANAGER.read_text()

    assert "const LIMIT = 1000;" in source
    assert "function commitVisible()" in source
    assert "Object.keys(next).length>LIMIT" in source


def test_shortcuts_do_not_interrupt_form_entry():
    source = quick_find_script()

    assert 'event.key === "Escape"' in source
    assert 'event.key !== "/"' in source
    assert "event.ctrlKey" in source
    assert "event.metaKey" in source
    assert "event.altKey" in source
    assert "target?.isContentEditable" in source
    assert '"INPUT", "TEXTAREA", "SELECT"' in source


def test_bulk_server_validation_is_preserved():
    source = (
        ROOT / "app/routers/vials.py"
    ).read_text()

    assert "def _bulk_validate(" in source
    assert "def _bulk_snapshot(" in source
    assert '"/vials/bulk/preview"' in source


def test_release_backup_and_smoke_are_preserved():
    source = (
        ROOT / "scripts/tracker-release.sh"
    ).read_text()

    assert "tracker-restore-verify.py" in source
    assert "tracker-runtime-smoke.py" in source
    assert "tracker-deployment-guard.py" in source
