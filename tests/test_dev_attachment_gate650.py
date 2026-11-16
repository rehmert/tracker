"""Release 650: DEV-only policy for unsynchronized uploads.

Missing files are advisory only on DEV when no migration is running;
invalid references, changed present files, and PROD remain fail-closed.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _gate():
    spec = spec_from_file_location(
        "tracker_dev_attachment_gate650",
        ROOT / "scripts/tracker-dev-attachment-gate650.py",
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(*, checked=32, missing=0, invalid=0, mismatch=0,
            status="PASSED"):
    details = (
        "MISSING_REFERENCE table=coa_attachments id=21 "
        "path=uploads/coa/example.png\n"
    ) * missing
    return (
        details +
        f"ATTACHMENT_REFERENCES_CHECKED={checked}\n"
        f"ATTACHMENT_FILES_MISSING={missing}\n"
        f"ATTACHMENT_REFERENCES_INVALID={invalid}\n"
        f"ATTACHMENT_HASH_MISMATCHES={mismatch}\n"
        f"ATTACHMENT_INTEGRITY={status}\n"
    )


def test_650_dev_missing_only_may_be_reported_without_mutation():
    gate = _gate()
    assert gate.classify(_report(), 0) == ("PASSED", 0)
    assert gate.classify(_report(missing=1, status="FAILED"), 1) == (
        "DEV_MISSING_ALLOWED", 1
    )


@pytest.mark.parametrize("stdout,code", [
    (_report(missing=1, invalid=1, status="FAILED"), 1),
    (_report(mismatch=1, status="FAILED"), 1),
    (_report(missing=1, status="FAILED"), 0),
    (_report(missing=1, status="PASSED"), 1),
    (_report(), 1),
    (_report(checked=0, missing=1, status="FAILED"), 1),
    (_report(missing=1, status="FAILED").replace(
        "MISSING_REFERENCE", "REF_MISSING"), 1),
    (_report() + "ATTACHMENT_INTEGRITY=PASSED\n", 0),
    (_report().replace("ATTACHMENT_FILES_MISSING=0\n", ""), 0),
    ("ATTACHMENT_INTEGRITY=FAILED: database missing\n", 1),
])
def test_650_dev_policy_fails_closed_on_bad_evidence(stdout, code):
    with pytest.raises(_gate().DevAttachmentError):
        _gate().classify(stdout, code)


def test_650_only_exact_dev_instance_is_eligible(tmp_path):
    gate = _gate()
    config = tmp_path / "tracker.env"
    config.write_text('TRACKER_INSTANCE="DEV"\n')
    gate.verify_dev_instance(config)
    for value in (
        'TRACKER_INSTANCE="PROD"\n',
        "TRACKER_INSTANCE=OTHER\n",
        "TRACKER_INSTANCE=DEV\nTRACKER_INSTANCE=DEV\n",
        "TRACKER_INSTANCE=DEV\nTRACKER_INSTANCE=PROD\n",
        "",
    ):
        config.write_text(value)
        with pytest.raises(gate.DevAttachmentError):
            gate.verify_dev_instance(config)


def test_650_runner_keeps_prod_and_migrations_strict():
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'if [[ "$INSTANCE" == DEV && "$DB_MIGRATION" == 0 ]]; then' in runner
    assert 'tracker-dev-attachment-gate650.py" --data "$LIVE_DATA_DIR"' in runner
    assert 'tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes' in runner
    assert 'LIVE_ATTACHMENT_PREFLIGHT=DEV_ONLY_MISSING_POLICY' in runner
    assert 'LIVE_ATTACHMENT_PREFLIGHT=PASSED' in runner


def test_650_preflight_uses_only_dev_gate_not_prod_uploads():
    text = (ROOT / "scripts/tracker-coa-preflight650.sh").read_text()
    assert 'tracker-dev-attachment-gate650.py --data /opt/tracker/data' in text
    assert 'COA_650_DEV_ATTACHMENTS=CHECKED_WITH_MISSING_FILE_POLICY' in text
    assert "prod" not in text.lower().split("=== DEV-ONLY ATTACHMENT AUDIT")[-1].split(
        "export TRACKER_DATA_DIR"
    )[0].replace("prod upload synchronization", "")
