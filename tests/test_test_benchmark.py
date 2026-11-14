"""Benchmark correctness and release-safety contracts."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/tracker-test-benchmark.py"

spec = importlib.util.spec_from_file_location(
    "tracker_test_benchmark", PATH
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_worker_selection_validation():
    assert benchmark.parse_workers(
        "1,2,4"
    ) == [1, 2, 4]
    assert benchmark.parse_workers(
        "8,12,16,24,32"
    ) == [8, 12, 16, 24, 32]
    assert benchmark.parse_workers("8") == [8]

    for invalid in (
        "1,1",
        "0,1",
        "1,33",
        "1,banana",
        "",
        "1,2,3,4,5,6,7,8,9",
    ):
        with pytest.raises(
            benchmark.argparse.ArgumentTypeError
        ):
            benchmark.parse_workers(invalid)


def test_parallel_recommended_only_with_meaningful_gain():
    selected, gain = benchmark.recommendation(
        {1: 40.0, 2: 34.0, 4: 28.0}
    )

    assert selected == 4
    assert gain == pytest.approx(0.30)

    selected, gain = benchmark.recommendation(
        {1: 40.0, 2: 38.0, 4: 37.0}
    )

    assert selected == 1
    assert gain == pytest.approx(0.075)


def test_second_stage_benchmark_uses_lowest_worker_as_baseline():
    # No need to waste another 10 minutes on a serial run after the
    # first 2,591-test benchmark established a reproducible baseline.
    selected, gain = benchmark.recommendation(
        {8: 101.12, 12: 85.0, 16: 70.0}
    )
    assert selected == 16
    assert gain == pytest.approx((101.12 - 70) / 101.12)

    selected, gain = benchmark.recommendation(
        {8: 101.12, 12: 100.0, 16: 99.0}
    )
    assert selected == 8
    assert gain < 0.10

    selected, gain = benchmark.recommendation(
        {8: 101.12, 12: 105.0, 16: 107.0}
    )
    assert selected == 8
    assert gain == 0.0

    selected, gain = benchmark.recommendation({8: 101.12})
    assert selected == 8
    assert gain == 0.0


def test_serial_is_kept_when_parallel_is_slower():
    selected, gain = benchmark.recommendation(
        {1: 30.0, 2: 31.0, 4: 33.0}
    )

    assert selected == 1
    assert gain == 0.0


def test_runner_uses_existing_isolated_test_modes():
    source = PATH.read_text()

    assert '"--full"' in source
    assert '"--parallel-check"' in source
    assert '"TRACKER_TEST_WORKERS"' in source
    assert "run_one(" in source
    assert "fully_qualified" in source
    assert '"baseline_workers": min(args.workers)' in source
    assert '"deployment_ready": False' in source
    assert "report.json" in source


def test_guarded_release_keeps_all_safety_gates_with_bounded_dev_parallelism():
    source = (ROOT / "scripts/tracker-release.sh").read_text()
    assert source.count('"$PY" -m pytest') == 1
    assert 'timeout 1200 "$PY" -m pytest' in source

    assert 'TEST_PYTEST_EXTRA=(-n 4 --dist=loadfile)' in source
    assert 'BACKEND_TEST_MODE=PARALLEL workers=4' in source
    assert "import xdist" in source
    assert 'fail "pytest-xdist missing; serial fallback prohibited"' in source
    assert 'TEST_PYTEST_EXTRA=()' not in source
    assert 'BACKEND_TEST_MODE=SERIAL reason=' not in source

    assert '--serial-tests) fail "Serial testing prohibited"' in source
    assert '[[ "$SERIAL_TESTS" == 0 ]]' in source
    assert '"$REF" "$SERIAL_TESTS"' in source
    assert '--durations=20 tests' in source
    assert 'MEMORY_PROPERTY="MemoryMax=2G"' in source
    assert 'verify_prod_approval' in source
    assert 'flock -n 9' in source
    assert 'INSTALLED_BYTECODE_REFRESH=PASSED' in source

    for marker in (
        "tracker-restore-verify.py",
        "tracker-deployment-guard.py",
        "tracker-runtime-smoke.py",
        "merge --ff-only",
        "reset --hard",
    ):
        assert marker in source
