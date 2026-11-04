#!/usr/bin/env bash
# Tracker development test runner.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${TRACKER_TEST_PYTHON:-/opt/tracker/.venv/bin/python}"

[[ -x "$PY" ]] || {
  echo "ERROR: Python unavailable: $PY" >&2
  exit 1
}

MODE="${1:---quick}"
if (( $# )); then shift; fi

case "$MODE" in
  --quick|--full|--profile|--one|--parallel-check) ;;
  *)
    echo "Usage: $0 --quick|--full|--profile|--one|--parallel-check [pytest args]" >&2
    exit 2
    ;;
esac

cd "$ROOT"
export PYTHONPATH="$ROOT"

COMMON=(
  -q
  --tb=short
  --maxfail=1
  --disable-warnings
)

BROWSER_EXCLUSIONS=(
  --ignore=tests/browser
  --ignore=tests/test_bulk_vial_browser.py
  --ignore=tests/test_bulk_vial_guided_browser.py
  --ignore=tests/test_bulk_delete_browser.py
  --ignore=tests/test_purchase_vial_browser.py
  --ignore=tests/test_stage33_browser_sorting.py
  --ignore=tests/test_health_timeline_dates_browser.py
  --ignore=tests/test_vitals_csv_browser.py
)

case "$MODE" in
  --quick)
    exec "$PY" -m pytest \
      "${COMMON[@]}" \
      tests/test_csrf_form_body_report.py \
      tests/test_request_origin_guard.py \
      tests/test_dose_sequential_workflow.py \
      tests/test_release_workflow.py \
      "$@"
    ;;
  --full)
    exec "$PY" -m pytest \
      "${COMMON[@]}" \
      --durations=20 \
      tests \
      "${BROWSER_EXCLUSIONS[@]}" \
      "$@"
    ;;
  --profile)
    exec "$PY" -m pytest \
      "${COMMON[@]}" \
      --durations=50 \
      --durations-min=0.1 \
      tests \
      "${BROWSER_EXCLUSIONS[@]}" \
      "$@"
    ;;
  --one)
    (( $# >= 1 )) || {
      echo "ERROR: Specify a test file or test node." >&2
      exit 2
    }
    exec "$PY" -m pytest \
      "${COMMON[@]}" "$@"
    ;;
  --parallel-check)
    WORKERS="${TRACKER_TEST_WORKERS:-2}"
    [[ "$WORKERS" =~ ^[1-8]$ ]] || {
      echo "ERROR: TRACKER_TEST_WORKERS must be 1-8." >&2
      exit 2
    }
    "$PY" -m pytest --help | grep -F -- '--dist=' >/dev/null || {
      echo "ERROR: pytest-xdist is not installed." >&2
      exit 2
    }
    echo "=== EXPERIMENTAL PARALLEL TESTING: $WORKERS WORKERS ==="
    echo "=== GUARDED DEPLOYMENTS REMAIN SERIAL ==="
    exec "$PY" -m pytest \
      "${COMMON[@]}" \
      -n "$WORKERS" --dist=loadfile \
      --durations=20 tests \
      "${BROWSER_EXCLUSIONS[@]}" "$@"
    ;;
esac
