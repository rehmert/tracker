"""Release 653: redacted, fail-closed DEV identity parsing contracts.

No host filesystem or credentials are read in these tests.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-instance-check653.py"


def instance_module():
    spec = importlib.util.spec_from_file_location("tracker_instance_check653", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("config", [
    "TRACKER_INSTANCE=DEV\n",
    "export TRACKER_INSTANCE='DEV'\n",
    'TRACKER_INSTANCE="dev" # instance comment\n',
    "  export  TRACKER_INSTANCE = DEV  # comment\n",
    "TRACKER_INSTANCE=DEV # trailing comment\n",
])
def test_653_instance_parser_accepts_shell_style_dev_labels(config):
    assert instance_module().parse_instance_values(config) == ["DEV"]


@pytest.mark.parametrize("config", [
    "",
    "TRACKER_INSTANCE=PROD\n",
    "TRACKER_INSTANCE=DEV\nTRACKER_INSTANCE=PROD\n",
    "TRACKER_INSTANCE=DEV extra\n",
    'TRACKER_INSTANCE="DEV\n',
    "TRACKER_INSTANCE=DEV; other_command\n",
])
def test_653_dev_verification_rejects_missing_non_dev_or_malformed_labels(
    tmp_path, config
):
    config_file = tmp_path / "tracker.env"
    config_file.write_text(config, encoding="utf-8")
    with pytest.raises(ValueError):
        instance_module().verify_dev(config_file, hostname="tracker-dev")


def test_653_dev_identity_requires_exact_host_and_does_not_echo_secrets(
    tmp_path, capsys
):
    config_file = tmp_path / "tracker.env"
    config_file.write_text(
        "TRACKER_INSTANCE='DEV' # staging\nDB_PASSWORD=super-secret\n",
        encoding="utf-8",
    )
    tool = instance_module()
    tool.verify_dev(config_file, hostname="tracker-dev")
    captured = capsys.readouterr()
    assert captured.out.strip() == "RELEASE_653_DEV_IDENTITY=VERIFIED"
    assert "super-secret" not in captured.out + captured.err
    with pytest.raises(ValueError, match="Expected tracker-dev"):
        tool.verify_dev(config_file, hostname="tracker-prod")
