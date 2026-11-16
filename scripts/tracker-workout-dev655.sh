#!/usr/bin/env bash
# Release 655: exact-SHA DEV-only workout deployment wrapper.
# Called on DEV's installed Release 654 checkout, never on PROD.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=419e0c199d6a5dc373df7de1401953a056cac8d1
REF=release/655-workout-routines-fast-logging
fail() { echo "WORKOUT_655_DEV=FAILED: $*" >&2; exit 1; }
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact approved 655 target SHA"
EXPECTED="$1"
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
  fail "Run as root on configured Tracker DEV"
[[ "$(hostname -s)" == tracker-dev ]] || fail "Only tracker-dev may run this wrapper"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "Installed checkout must be a clean main branch"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] ||
  fail "Installed DEV must be at Release 654"
systemctl is-active --quiet tracker || fail "Tracker DEV service not running"
"$PY" "$APP/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV instance identity not verified"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Candidate branch differs from pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate is not descended from 654"
RUN="$(mktemp -d /tmp/tracker-workout655-runner.XXXXXXXX)"
cleanup() { rm -f "$RUN/runner.sh"; rmdir "$RUN" 2>/dev/null || true; }
trap cleanup EXIT
EXPECTED_BLOB="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$RUN/runner.sh"
[[ "$(g hash-object "$RUN/runner.sh")" == "$EXPECTED_BLOB" ]] ||
  fail "Release runner differs from pinned candidate"
bash -n "$RUN/runner.sh"
echo "WORKOUT_655_DEV_TARGET=$TARGET"
echo "WORKOUT_655_SCHEMA_MIGRATION=REVIEWED_AND_BACKUP_REQUIRED"
echo "WORKOUT_655_TEST_MODE=CHANGE_SCOPED"
bash "$RUN/runner.sh" \
  --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF" \
  --db-migration --reviewed-workout-655
