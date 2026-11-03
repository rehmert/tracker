"""Quality gate and route auditing contracts."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_quality_gate_source_only_passes():
    result = run(
        ROOT / "scripts/tracker-quality-gate.py",
        "--source-only",
    )
    assert result.returncode == 0, (
        result.stdout[-2000:] + result.stderr
    )
    assert (
        "Managed source asset vendor/htmx.min.js"
        in result.stdout
        or "Static asset vendor/htmx.min.js"
        in result.stdout
    )


def test_runtime_gate_does_not_silently_skip_vendor():
    path = ROOT / "scripts/tracker-quality-gate.py"
    source = path.read_text()

    assert "args.source_only" in source
    assert 'name == "vendor/htmx.min.js"' in source
    assert "managed_htmx_source_is_configured()" in source
    assert "not exists" in source


def test_effective_routes_are_distinct():
    path = ROOT / "scripts/tracker-route-audit.py"
    result = run(path)

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )
    assert (
        "PASS: No duplicate effective route paths"
        in result.stdout
    )


def test_prefixes_are_known():
    from importlib.util import (
        module_from_spec, spec_from_file_location
    )

    path = ROOT / "scripts/tracker-route-audit.py"
    spec = spec_from_file_location(
        "tracker_route_audit", path
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    routes = module.analyze()
    keys = {
        (row["method"], row["path"])
        for row in routes
    }

    assert ("POST", "/compounds") in keys
    assert ("POST", "/pk/compounds") in keys
    assert ("GET", "/vials") in keys
    assert (
        "GET", "/record-explorer/vials"
    ) in keys


def test_pytest_import_mode():
    ini = (ROOT / "pytest.ini").read_text()
    assert "addopts = --import-mode=importlib" in ini


def test_scripts_parse():
    for name in (
        "tracker-route-audit.py",
        "tracker-quality-gate.py",
    ):
        path = ROOT / "scripts" / name
        ast.parse(path.read_text())
