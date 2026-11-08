#!/usr/bin/env bash
# Legacy compatibility entry point for Tracker tests.
# The canonical non-browser runner is scripts/tracker-test.sh.
# Browser mutation tests must only run on a detached disposable candidate.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PY="$ROOT/.venv/bin/python"
MODE="${1:-quick}"
if (( $# )); then shift; fi

case "$MODE" in
  quick)
    exec bash "$ROOT/scripts/tracker-test.sh" --quick "$@"
    ;;
  full)
    exec bash "$ROOT/scripts/tracker-test.sh" --full "$@"
    ;;
  profile)
    exec bash "$ROOT/scripts/tracker-test.sh" --profile "$@"
    ;;
  browser|live)
    (( $# == 0 )) || { echo "ERROR: Unexpected arguments" >&2; exit 2; }
    exec bash "$ROOT/scripts/tracker-test-gate475.sh" browser
    ;;
  all|release)
    (( $# == 0 )) || { echo "ERROR: Unexpected arguments" >&2; exit 2; }
    [[ -n "${TRACKER_BROWSER_CANDIDATE:-}" ]] || {
      echo "ERROR: Complete qualification requires TRACKER_BROWSER_CANDIDATE." >&2
      echo "Use the guarded tracker-release.sh flow for deployment acceptance." >&2
      exit 2
    }
    bash "$ROOT/scripts/tracker-test.sh" --full
    exec bash "$ROOT/scripts/tracker-test-gate475.sh" browser
    ;;
  none)
    [[ -x "$PY" ]] || { echo "ERROR: Python missing" >&2; exit 2; }
    exec "$PY" -m compileall -q "$ROOT/app" "$ROOT/scripts" "$ROOT/tests"
    ;;
  *)
    echo "Usage: $0 {quick|full|profile|browser|live|all|release|none}" >&2
    exit 2
    ;;
esac
