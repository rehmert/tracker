"""Release 648: exact-SHA recovery from promoted-but-not-installed 647."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_promote568.py"
OLD = "cd041ba1dfefe6e2de7db72c8bfdf8f9949e6dc6"
BASE = "61b3016eed48527c61a5173d94ee0f58b859f81a"
TARGET = "e" * 40


def _module():
    spec = spec_from_file_location("tracker_promote648_test", SCRIPT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_648_only_exact_previously_promoted_main_is_eligible(monkeypatch):
    module = _module()
    calls = []
    monkeypatch.setattr(module, "run", lambda cmd, **kwargs: calls.append(cmd))
    assert module.recovery_648_main_allowed(OLD, TARGET, BASE) is True
    assert len(calls) == 2
    assert all("--is-ancestor" in command for command in calls)
    assert [command[-2:] for command in calls] == [[BASE, OLD], [OLD, TARGET]]
    for main, base in (
        ("f" * 40, BASE), (BASE, BASE), (OLD, OLD),
        ("a" * 40, "a" * 40),
    ):
        assert module.recovery_648_main_allowed(main, TARGET, base) is False
    assert len(calls) == 2


def test_648_ancestry_failure_never_enables_recovery(monkeypatch):
    module = _module()
    def deny(_command):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(module, "run", deny)
    assert module.recovery_648_main_allowed(OLD, TARGET, BASE) is False


def test_648_fast_forward_promotion_only_never_force_push(monkeypatch):
    module = _module()
    seen = []
    main_results = iter([OLD, TARGET])
    monkeypatch.setattr(module, "git", lambda *args: next(main_results))
    monkeypatch.setattr(module, "recovery_648_main_allowed",
                        lambda main, target, base: (main, target, base) == (OLD, TARGET, BASE))
    monkeypatch.setattr(module, "run", lambda command, **kwargs: seen.append(command))
    module.promote(TARGET, BASE)
    pushes = [cmd for cmd in seen if "push" in cmd]
    assert len(pushes) == 1
    assert pushes[0][-2:] == ["origin", TARGET + ":refs/heads/main"]
    assert not any("--force" in value for cmd in seen for value in cmd)


def test_648_other_intermediate_main_fails_before_push(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "git", lambda *args: "f" * 40)
    monkeypatch.setattr(module, "recovery_648_main_allowed", lambda *args: False)
    calls = []
    monkeypatch.setattr(module, "run", lambda command, **kwargs: calls.append(command))
    with pytest.raises(module.ReleaseError, match="GitHub main moved"):
        module.promote(TARGET, BASE)
    assert not any("push" in cmd for cmd in calls)


def test_648_historical_csrf_witnesses_stay_unqualified():
    from scripts.tracker_csrf_runtime_report579 import reviewed_js_source_callsites
    report = reviewed_js_source_callsites(ROOT)
    assert report["tracked_js_callsites"] == 51
    assert report["witnessed_js_callsites"] == 2
    assert report["not_witnessed_in_579"] == 49
    assert report["unqualified_coa_multi651_callsites"] == 1
    assert report["unqualified_workout_offline668_callsites"] == 1
    from scripts.tracker_csrf_route_ledger578 import build
    ledger = build(ROOT)
    assert ledger["summary"]["javascript_callsites"] == 51
    assert ledger["summary"]["js_runtime_verified"] == 0
    assert any(row["file"] == "app/static/js/tracker-coa-types647.js"
               for row in ledger["javascript"])
