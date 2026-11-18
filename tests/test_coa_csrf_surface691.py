"""Release 691: verify no change to historical JavaScript request inventory.

The historical Release 651 test pins an obsolete global absolute count (50)
and is deliberately NOT used as a Release 691 scoped release gate. Instead
prove no new JS or template fetch callsites were introduced since Release 690
and that the exact reviewed Release 651 AJAX POST source contract is intact.
This is source inventory, not runtime CSRF certification.
"""
from pathlib import Path
import re
import subprocess

from scripts.tracker_csrf_runtime_report579 import (
    COA_MULTI651_REQUEST_LINES,
    COA_MULTI651_SOURCE,
    TRACKED_FETCH_SOURCES,
    verify_coa_multi651_request_lines,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = "6a8cd357e7e8925228d1a37c50572f93c4ec0943"
REQUEST = re.compile(r"\bfetch\s*\(|\bhtmx\.ajax\s*\(")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def request_source_lines(text):
    # Scanner intentionally matches source lines, including inline templates.
    return [
        line.strip() for line in text.splitlines() if REQUEST.search(line)
    ]


def test_691_no_new_js_or_inline_template_request_callsites():
    changed = git("diff", "--name-only", BASE, "HEAD").splitlines()
    assert "app/templates/coa_edit.html" in changed
    assert not any(
        path.startswith("app/static/") and path.endswith(".js")
        for path in changed
    ), "Release 691 must not modify JavaScript request sources"
    assert not any(
        path.startswith("app/templates/")
        and path.endswith(".html")
        and path != "app/templates/coa_edit.html"
        for path in changed
    ), "Unexpected additional template changes"
    before = git("show", f"{BASE}:app/templates/coa_edit.html")
    after = (ROOT / "app/templates/coa_edit.html").read_text(encoding="utf-8")
    assert request_source_lines(before) == request_source_lines(after) == []
    assert "window.fetch" not in after
    assert 'method="post" action="/coas/{{ coa.id }}/attachments/identifiers"' in after


def test_691_existing_reviewed_coa_ajax_request_contract_remains_exact():
    assert COA_MULTI651_SOURCE not in TRACKED_FETCH_SOURCES
    source = (ROOT / COA_MULTI651_SOURCE).read_text(encoding="utf-8")
    lines = source.splitlines()
    occurrences = [
        n for n, line in enumerate(lines)
        if line.strip() == COA_MULTI651_REQUEST_LINES[0]
    ]
    assert len(occurrences) == 1
    verify_coa_multi651_request_lines(lines, occurrences[0])
    assert source == git("show", f"{BASE}:{COA_MULTI651_SOURCE}")


def test_691_existing_csrf_inventory_scanners_unchanged():
    for path in (
        "scripts/tracker_csrf_runtime_report579.py",
        "scripts/tracker_csrf_js_review575.py",
        "scripts/tracker_csrf_js_triage576.py",
        "scripts/tracker-csrf-readiness.py",
        "scripts/tracker_csrf_route_ledger578.py",
    ):
        assert (ROOT / path).read_text(encoding="utf-8") == git(
            "show", f"{BASE}:{path}"
        )
