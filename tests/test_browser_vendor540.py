"""Release 540: isolated browser QA asset reuse."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-browser-qualify.sh"
TRUSTED = Path("/opt/tracker/app/static/vendor/htmx.min.js")


def prepare(tmp_path):
    candidate = tmp_path / "candidate"
    (candidate / "app/static/vendor").mkdir(parents=True)
    (candidate / "app/main.py").write_text("# fixture\n")
    return candidate


def run_prelude(candidate):
    source = SCRIPT.read_text()
    marker = 'ROOT="$(mktemp -d /tmp/tracker-browser-qa.XXXXXXXX)"'

    assert source.count(marker) == 1

    # Execute only the actual browser script's asset
    # preparation section, before it launches a server.
    prelude = source.split(marker, 1)[0]

    return subprocess.run(
        [
            "bash", "-c", prelude,
            "tracker-browser-qualify.sh",
            str(candidate), "/bin/true",
        ],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_missing_asset_is_copied540(tmp_path):
    assert TRUSTED.is_file()

    candidate = prepare(tmp_path)
    result = run_prelude(candidate)

    assert result.returncode == 0, result.stderr
    assert "ISOLATED_HTMX_VENDOR=COPIED_VERIFIED" in result.stdout

    asset = candidate / "app/static/vendor/htmx.min.js"

    assert asset.read_bytes() == TRUSTED.read_bytes()


def test_identical_asset_is_reused540(tmp_path):
    assert TRUSTED.is_file()

    candidate = prepare(tmp_path)
    asset = candidate / "app/static/vendor/htmx.min.js"
    asset.write_bytes(TRUSTED.read_bytes())

    result = run_prelude(candidate)

    assert result.returncode == 0, result.stderr
    assert "ISOLATED_HTMX_VENDOR=REUSED_VERIFIED" in result.stdout
    assert asset.read_bytes() == TRUSTED.read_bytes()


def test_modified_asset_is_rejected540(tmp_path):
    candidate = prepare(tmp_path)
    asset = candidate / "app/static/vendor/htmx.min.js"
    asset.write_bytes(b"untrusted vendor content")

    result = run_prelude(candidate)

    assert result.returncode != 0
    assert "differs from trusted source" in result.stderr
    assert asset.read_bytes() == b"untrusted vendor content"


def test_symlink_asset_is_rejected540(tmp_path):
    candidate = prepare(tmp_path)
    asset = candidate / "app/static/vendor/htmx.min.js"

    asset.symlink_to(TRUSTED)

    result = run_prelude(candidate)

    assert result.returncode != 0
    assert "not a regular file" in result.stderr
    assert asset.is_symlink()


def test_browser_fixture_remains_isolated540():
    source = SCRIPT.read_text()

    assert '[[ "$SOURCE" != /opt/tracker' in source
    assert 'TRACKER_DATA_DIR="$DATA"' in source
    assert "ISOLATED_HTMX_VENDOR=REUSED_VERIFIED" in source
    assert "ISOLATED_HTMX_VENDOR=COPIED_VERIFIED" in source
    assert "cmp -s" in source
