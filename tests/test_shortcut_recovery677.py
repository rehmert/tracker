"""Release 677: tightly scoped recovery of signed Release 676 promotion."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_promote568.py"
spec = importlib.util.spec_from_file_location("promote_677", SCRIPT)
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)

PROD_675 = "2e8f65d7c61c522a5ab01f78cd3783e15559ece3"
PROMOTED_676 = "3646f5ebf39f0b0ff2759c35e75df46120a72c7c"
TARGET = "a" * 40


def test_677_recovery_is_pinned_to_exact_baselines_and_ancestry():
    with patch.object(promote, "run") as run:
        assert promote.recovery_677_main_allowed(PROMOTED_676, TARGET, PROD_675)
        assert run.call_count == 2  # base -> main -> target ancestry
        assert any("merge-base" in call.args[0] for call in run.call_args_list)
        run.reset_mock()
        for main, base in (
            ("b" * 40, PROD_675),
            (PROMOTED_676, "c" * 40),
            ("d" * 40, "e" * 40),
        ):
            assert not promote.recovery_677_main_allowed(main, TARGET, base)
        assert run.call_count == 0


def test_677_normal_promoter_remains_fail_closed_and_signed():
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'release == 677 and recovery_677_main_allowed(' in src
    assert 'release == 648 and recovery_648_main_allowed(' in src
    assert 'if main not in (base, target) and not (allowed_648 or allowed_677):' in src
    assert 'PROD_RECOVERY_677_ANCESTOR_VERIFIED=' in src
    assert 'verify_dev' in src or 'verified_log(' in src
    assert '"merge-base", "--is-ancestor", main, target' in src
    launcher = (ROOT / "scripts/tracker-release677.sh").read_text()
    assert f'BASE677={PROMOTED_676}' in launcher
    assert launcher.count(f'[[ "$PROD_BASE" == "{PROD_675}" ]]') == 2
    assert '--release 677 --target "$TARGET" --prod-base "$PROD_BASE"' in launcher
    assert 'git hash-object "$STAGE/runner.sh"' in launcher
    assert 'tracker_promote568.py' in launcher
    assert 'git push -f' not in launcher
