"""Release 569: offline contracts for observed dependency baseline.

The tests never install packages or run pip against an installed Tracker host.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_dependency_baseline569.py"
MANIFEST = ROOT / "docs/dependencies/observed-2026-11-11-py313.json"
CONSTRAINTS = ROOT / "docs/dependencies/candidate-constraints-py313.txt"


@pytest.fixture
def audit():
    spec = importlib.util.spec_from_file_location("baseline569", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_observed_baseline_is_consistent_and_never_active_requirements(audit):
    observed = audit.read_manifest(MANIFEST)
    pins = audit.read_constraints(CONSTRAINTS)
    audit.validate_constraints(observed, pins)
    assert observed["python"] == "3.13.5"
    assert observed["sqlite"] == "3.46.1"
    assert len(observed["packages"]) == 44
    assert len(pins) == 43
    assert observed["packages"]["pip"] == "25.1.1"
    assert observed["packages"]["fastapi"] == "0.162.0"
    assert observed["packages"]["sqlalchemy"] == "2.1.6"
    assert observed["packages"]["playwright"] == "1.64.1"
    assert "pip" not in pins
    assert "requirements" not in CONSTRAINTS.name
    for filename in ("requirements.txt", "requirements-dev.txt"):
        assert (ROOT / filename).is_file()


def test_reported_package_names_follow_normalized_pep503_spelling(audit):
    assert audit.canonical("Pydantic_Core") == "pydantic-core"
    assert audit.canonical("PyTest.XDist") == "pytest-xdist"
    assert audit.normalize_versions({"Pydantic_Core": "2.50.1"}) == {
        "pydantic-core": "2.50.1"
    }
    with pytest.raises(audit.BaselineError):
        audit.normalize_versions({"Py_Test": "1", "py-test": "2"})
    with pytest.raises(audit.BaselineError):
        audit.normalize_versions({"name": "1 ; evil"})


def test_constraint_parser_refuses_unpinned_and_duplicate_entries(tmp_path, audit):
    path = tmp_path / "constraints.txt"
    # Foo and Foo_ canonicalize to different names; this is not a duplicate.
    # PEP 503 normalizes Foo_Bar and foo-bar to the SAME package name.
    for unsafe in (
        "fastapi>=0.1\n",
        "--extra-index-url https://example.invalid\n",
        "Foo_Bar==1\nfoo-bar==2\n",
        "foo==1\nfoo==2\n",
    ):
        path.write_text(unsafe, encoding="utf-8")
        with pytest.raises(audit.BaselineError):
            audit.read_constraints(path)


def test_diff_detects_missing_extra_version_python_and_sqlite(audit):
    expected = {
        "python": "3.13.5",
        "sqlite": "3.46.1",
        "packages": {"pip": "25.1.1", "fastapi": "0.162.0"},
    }
    assert audit.compare(
        expected, dict(expected["packages"]), "3.13.5", "3.46.1"
    ) == []
    findings = audit.compare(
        expected, {"fastapi": "0.163.0", "unexpected": "1.0"}, "3.13.6", "3.47.0"
    )
    assert len(findings) == 5
    assert any("PACKAGE pip" in line for line in findings)
    assert any("PACKAGE unexpected" in line for line in findings)
    assert any("PACKAGE fastapi" in line for line in findings)


def test_read_only_audit_returns_zero_for_match_and_two_for_drift(audit, monkeypatch, capsys):
    baseline = audit.read_manifest(MANIFEST)
    monkeypatch.setattr(audit, "pip_packages", lambda: dict(baseline["packages"]))
    monkeypatch.setattr(audit.platform, "python_version", lambda: baseline["python"])
    monkeypatch.setattr(audit.sqlite3, "sqlite_version", baseline["sqlite"])

    def clean_check(command, **kwargs):
        assert command[-2:] == ["pip", "check"]
        assert kwargs.get("check") is False
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(audit.subprocess, "run", clean_check)
    assert audit.main(["--instance", "DEV"]) == 0
    assert "BASELINE_AUDIT=PASS" in capsys.readouterr().out

    changed = dict(baseline["packages"])
    changed["fastapi"] = "9.9.9"
    monkeypatch.setattr(audit, "pip_packages", lambda: changed)
    assert audit.main(["--instance", "PROD"]) == 2
    assert "BASELINE_AUDIT=DRIFT" in capsys.readouterr().out


def test_audit_source_contains_no_install_upgrade_or_service_mutation():
    source = SCRIPT.read_text(encoding="utf-8")
    for prohibited in (
        '"install"', '"uninstall"', '"upgrade"', '"systemctl"', '"restart"',
        "os.environ", "shutil.rmtree", "write_text(", "write_bytes(",
    ):
        assert prohibited not in source
    assert '["pip", "list", "--format=json"]' not in source  # uses interpreter pin
    assert '"pip", "list", "--format=json"' in source
    assert '"pip", "check"' in source
