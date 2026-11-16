#!/usr/bin/env bash
# Release 664: DEV-only, exact-SHA source-only Workout deployment.
# Fetches code from GitHub. All tests run on tracker-dev; no GitHub CI.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=20b9c0599ebf9ff4ea05ccddcd7130beaf6027a1
REF=release/664-workout-calendar
fail() { echo "WORKOUT_664_DEV=FAILED: $*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact Release 664 SHA"
EXPECTED="$1"
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
  fail "Must run as root on configured Tracker DEV"
[[ "$(hostname -s)" == tracker-dev ]] || fail "Run only on tracker-dev"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] ||
  fail "Installed DEV must be qualified Release 663"
systemctl is-active --quiet tracker || fail "Tracker DEV service not active"
"$PY" "$APP/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV instance identity not verified"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Candidate differs from pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not descended from Release 663"

RUN="$(mktemp -d /tmp/tracker-workout664-runner.XXXXXXXX)"
cleanup() { rm -f "$RUN/runner.sh"; rmdir "$RUN" 2>/dev/null || true; }
trap cleanup EXIT
EXPECTED_BLOB="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$RUN/runner.sh"
[[ "$(g hash-object "$RUN/runner.sh")" == "$EXPECTED_BLOB" ]] ||
  fail "Release runner source differs from pinned candidate"
bash -n "$RUN/runner.sh"
echo "WORKOUT_664_DEV_TARGET=$TARGET"
echo "WORKOUT_664_SCHEMA_MIGRATION=NONE"
echo "WORKOUT_664_TEST_MODE=CHANGE_SCOPED"
bash "$RUN/runner.sh" \
  --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
