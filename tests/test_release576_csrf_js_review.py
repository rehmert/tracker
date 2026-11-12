"""Release 576: fail-closed source review regression coverage."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_review576.py"


@pytest.fixture(scope="module")
def review576():
    spec = importlib.util.spec_from_file_location("csrf_review576", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("snippet,expected,method,target", [
    (
        "fetch('/vitals', {method: 'POST', body: data});",
        "explicit_unsafe", "POST", "/vitals",
    ),
    (
        "fetch('/food/barcode/123'); const unused = {method:'POST'};",
        "implicit_get_url_expression", "GET", "/food/barcode/123",
    ),
    (
        "fetch('/food/barcode/' + encodeURIComponent(barcode));",
        "implicit_get_url_expression", "GET", None,
    ),
    (
        "fetch(url, {method: chosenMethod, body: payload});",
        "dynamic_method", None, None,
    ),
    (
        "fetch(new Request('/vitals', {method:'POST'}));",
        "request_or_options_unresolved", None, None,
    ),
    (
        "fetch(url, {cache: 'no-store'});",
        "request_or_options_unresolved", None, None,
    ),
    (
        "fetch('/vitals', {method: 'GET'});",
        "explicit_get", "GET", "/vitals",
    ),
    (
        "fetch('/vitals', {headers: {method:'POST'}, cache: 'no-store'});",
        "implicit_get_url_expression", "GET", "/vitals",
    ),
    (
        "fetch('/vitals', {method:'POST', ...overrides});",
        "dynamic_method", None, "/vitals",
    ),
])
def test_576_callsite_parsing_does_not_borrow_unrelated_methods(
    review576, tmp_path, snippet, expected, method, target,
):
    file = tmp_path / "app/static/qa.js"
    file.parent.mkdir(parents=True)
    file.write_text(snippet + "\n", encoding="utf-8")
    row = review576.analyze_callsite(
        {"file": "app/static/qa.js", "line": 1, "kind": "fetch_callsite",
         "classification": "release_575_hint_only"}, tmp_path,
    )
    assert row["method_source_class"] == expected, row
    assert row["literal_method"] == method
    assert row["exact_literal_target"] == target
    assert not row["runtime_compatibility_verified"]


def test_576_nested_object_and_multiline_fetch_is_extracted(review576, tmp_path):
    source = (
        "const response = await fetch(\n"
        "  '/vials/bulk/validate-selection',\n"
        "  {method: 'POST', body: makeBody({foo: [1, 2]})}\n"
        ");\n"
    )
    file = tmp_path / "app/static/qa.js"
    file.parent.mkdir(parents=True)
    file.write_text(source, encoding="utf-8")
    row = review576.analyze_callsite(
        {"file": "app/static/qa.js", "line": 1, "kind": "fetch_callsite",
         "classification": "old"}, tmp_path,
    )
    assert row["method_source_class"] == "explicit_unsafe"
    assert row["exact_literal_target"] == "/vials/bulk/validate-selection"


def test_576_htmx_uses_verb_as_first_argument(review576, tmp_path):
    file = tmp_path / "app/static/qa.js"
    file.parent.mkdir(parents=True)
    file.write_text("htmx.ajax('DELETE', '/vitals/1');\n", encoding="utf-8")
    row = review576.analyze_callsite(
        {"file": "app/static/qa.js", "line": 1,
         "kind": "htmx_ajax_callsite", "classification": "old"}, tmp_path,
    )
    assert row["method_source_class"] == "htmx_explicit_unsafe"
    assert row["literal_method"] == "DELETE"
    assert row["exact_literal_target"] == "/vitals/1"


def test_576_source_file_must_be_inside_repo(review576, tmp_path):
    with pytest.raises(ValueError, match="escaped source root"):
        review576.analyze_callsite(
            {"file": "../../etc/passwd", "line": 1,
             "kind": "fetch_callsite", "classification": "old"}, tmp_path,
        )


def test_576_every_js_callsite_and_route_remains_reviewable(review576):
    report = review576.build(ROOT)
    assert report["status"] == (
        "SOURCE_REVIEW_ONLY_STRICT_ENFORCEMENT_NOT_AUTHORIZED"
    )
    assert report["summary"]["js_request_callsites"] == 46
    assert len(report["javascript"]) == 46
    assert sum(report["summary"]["js_method_source_classes"].values()) == 46
    assert (
        report["summary"]["explicit_unsafe_source_callsites"]
        + report["summary"]["other_or_unresolved_source_callsites"]
    ) == 46
    assert report["summary"]["static_unsafe_route_declarations"] > 90
    assert len(report["static_routes"]) > 90
    assert all(
        not route["browser_test_run_verified"]
        and route["manual_verification_outstanding"]
        for route in report["static_routes"]
    )
    assert all(
        not row["runtime_compatibility_verified"]
        for row in report["javascript"]
    )
    assert any(
        row["method_source_class"] == "explicit_unsafe"
        for row in report["javascript"]
    )
    assert any(
        row["method_source_class"] != "explicit_unsafe"
        for row in report["javascript"]
    )
    assert any(
        row["path"] == "/vials/bulk/delete-preview"
        and "576" in (row["browser_test_defined"] or "")
        for row in report["static_routes"]
    )


def test_576_private_json_output_is_confined(review576, tmp_path):
    with tempfile.TemporaryDirectory(
        prefix="tracker-csrf576.", dir="/tmp"
    ) as directory:
        destination = Path(directory) / "review.json"
        assert review576.main(["--json", str(destination)]) == 0
        assert destination.is_file()
        assert destination.stat().st_mode & 0o077 == 0

    with pytest.raises(SystemExit) as exc:
        review576.main(["--json", str(tmp_path / "review.json")])
    assert exc.value.code == 2
