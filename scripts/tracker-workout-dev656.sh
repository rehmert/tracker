#!/usr/bin/env bash
# Release 656: DEV-only, exact-SHA source-only Workout deployment.
# Fetches code from GitHub. All tests run on tracker-dev; no GitHub CI.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25
REF=release/656-workout-qr-progress
fail() { echo "WORKOUT_656_DEV=FAILED: $*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact Release 656 SHA"
EXPECTED="$1"
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
  fail "Must run as root on configured Tracker DEV"
[[ "$(hostname -s)" == tracker-dev ]] || fail "Run only on tracker-dev"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] ||
  fail "Installed DEV must be qualified Release 655"
systemctl is-active --quiet tracker || fail "Tracker DEV service not active"
"$PY" "$APP/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV instance identity not verified"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Candidate differs from pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not descended from Release 655"

RUN="$(mktemp -d /tmp/tracker-workout656-runner.XXXXXXXX)"
cleanup() { rm -f "$RUN/runner.sh"; rmdir "$RUN" 2>/dev/null || true; }
trap cleanup EXIT
EXPECTED_BLOB="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$RUN/runner.sh"
[[ "$(g hash-object "$RUN/runner.sh")" == "$EXPECTED_BLOB" ]] ||
  fail "Release runner source differs from pinned candidate"
bash -n "$RUN/runner.sh"
echo "WORKOUT_656_DEV_TARGET=$TARGET"
echo "WORKOUT_656_SCHEMA_MIGRATION=NONE"
echo "WORKOUT_656_TEST_MODE=CHANGE_SCOPED"
bash "$RUN/runner.sh" \
  --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
