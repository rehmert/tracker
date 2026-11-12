"""Release 575: executable tests for the read-only JS CSRF callsite queue."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_js_review575.py"


@pytest.fixture(scope="module")
def review575():
    spec = importlib.util.spec_from_file_location("csrf_js_review575", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_575_full_js_source_inventory_is_preserved(review575):
    report = review575.build(ROOT)
    summary = report["summary"]
    assert report["status"] == "source_triage_only_not_security_clearance"
    assert summary["js_request_callsites"] == 46
    assert summary["unreviewed_runtime_effects"] == 46
    assert sum(summary["classes"].values()) == 46
    assert len(report["callsites"]) == 46
    assert all(
        (ROOT / row["file"]).is_file()
        for row in report["callsites"]
    )
    assert any(
        item["classification"] == "unsafe_method_literal_nearby"
        for item in report["callsites"]
    )
    assert "Every JavaScript write remains subject to real-browser acceptance tests" in report["limitations"]


@pytest.mark.parametrize("snippet,category", [
    (
        "const response = await fetch('/vitals', {\n"
        "  method: 'POST',\n  body: payload\n});\n",
        "unsafe_method_literal_nearby",
    ),
    (
        "const response = await fetch(url, {\n"
        "  method: dynamicMethod,\n});\n",
        "dynamic_method_manual_review",
    ),
    (
        "const response = await fetch(url, {\n"
        "  cache: 'no-store'\n});\n",
        "no_unsafe_literal_nearby_manual_review",
    ),
])
def test_575_source_nearby_method_is_a_hint_not_security_proof(
    review575, tmp_path, snippet, category,
):
    file = tmp_path / "app/static/qa.js"
    file.parent.mkdir(parents=True)
    file.write_text(snippet, encoding="utf-8")
    entry = review575.classify_callsite({
        "kind": "fetch_callsite",
        "file": "app/static/qa.js",
        "line": 1,
    }, tmp_path)
    assert entry["classification"] == category
    assert len(entry["source_line"]) <= 220


def test_575_no_relative_source_path_escape(review575, tmp_path):
    with pytest.raises(ValueError, match="escaped repository"):
        review575.classify_callsite({
            "kind": "fetch_callsite",
            "file": "../../etc/passwd",
            "line": 1,
        }, tmp_path)


def test_575_review_json_is_private_and_confined_to_sandbox(review575):
    with tempfile.TemporaryDirectory(
        dir="/tmp", prefix="tracker-csrf575."
    ) as directory:
        destination = Path(directory) / "js-review.json"
        assert review575.main(["--json", str(destination)]) == 0
        assert destination.is_file()
        assert destination.stat().st_mode & 0o077 == 0


def test_575_review_json_refuses_other_output_locations(review575, tmp_path):
    with pytest.raises(SystemExit) as exc:
        review575.main(["--json", str(tmp_path / "js-review.json")])
    assert exc.value.code == 2
