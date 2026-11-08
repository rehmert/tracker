"""Release 504: profiling diagnostics cannot weaken privacy or security."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-secondary-profile504.py"
spec = importlib.util.spec_from_file_location("secondary_profile504", SCRIPT)
profiler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = profiler
spec.loader.exec_module(profiler)


def test_504_profile_targets_real_release440_security_tests():
    assert set(profiler.TARGETS) == {"workflow", "readiness"}
    assert profiler.TARGETS["workflow"] == (
        "tests/test_secondary_private_workflow440.py::"
        "test_full_private_browser_workflow_with_audits_and_no_cross_account_data"
    )
    assert profiler.TARGETS["readiness"] == (
        "tests/test_secondary_integration440.py::"
        "test_authenticated_readiness_matches_every_runtime_flag"
    )
    for node in profiler.TARGETS.values():
        path, _, test_name = node.partition("::")
        assert (ROOT / path).is_file()
        assert f"def {test_name}(" in (ROOT / path).read_text()


def test_504_profile_recognizes_only_isolated_workers():
    assert profiler.worker_command([
        sys.executable, "-m", "app.worker_read429"
    ]) == "app.worker_read429"
    for cmd in (
        None,
        "python -m app.worker_read429",
        [sys.executable, "-m"],
        [sys.executable, "-m", "pytest"],
        [sys.executable, "-m", "app.main"],
    ):
        assert profiler.worker_command(cmd) is None


def test_504_profile_records_timings_without_request_secrets(monkeypatch, capsys):
    def fake_request(_client, _method, _url, *_args, **_kwargs):
        return SimpleNamespace(status_code=200)

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    monkeypatch.setattr(subprocess, "run", fake_run)

    recorder = profiler.TimingRecorder()
    recorder.install()
    try:
        httpx.Client.request(
            object(), "GET",
            "https://tracker.test/secondary/overview?secret=not-for-log",
        )
        httpx.Client.request(
            object(), "GET", "https://tracker.test/non-secondary",
        )
        subprocess.run(
            [sys.executable, "-m", "app.worker_read429"],
            input="password=not-for-log",
        )
    finally:
        recorder.uninstall()

    assert len(recorder.requests) == 1
    assert len(recorder.workers) == 1
    assert recorder.requests[0][1] == "/secondary/overview"
    recorder.report()
    printed = capsys.readouterr().out
    assert "SECONDARY_HTTP_COUNT=1" in printed
    assert "SECONDARY_WORKER_COUNT=1" in printed
    assert "app.worker_read429" in printed
    assert "not-for-log" not in printed
    assert "secret=" not in printed
    assert "password=" not in printed


def test_504_profiler_cannot_start_on_prod_or_live_checkout():
    source = SCRIPT.read_text()
    assert 'socket.gethostname().split(".")[0] != "tracker-dev"' in source
    assert 'ROOT.resolve() == Path("/opt/tracker").resolve()' in source
    assert 'if not (ROOT / "tests/conftest.py").is_file():' in source
    assert 'import app.' not in source.split("def main(")[0]
