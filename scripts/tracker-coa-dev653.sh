#!/usr/bin/env bash
# Release 653: SHA-pinned guarded code-only DEV deployment; no full suite.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=f342c81b32cf6a627b3958f45580315a08590a58
REF=release/653-coa-test-type-actions-row
fail() { echo "COA_653_DEV=FAILED: $*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact target SHA"
EXPECTED="$1"
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" ]] ||
  fail "Run as root on configured DEV"
[[ "$(hostname -s)" == tracker-dev ]] ||
  fail "Expected tracker-dev host; deployment blocked"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "Installed DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be at Release 652"
systemctl is-active --quiet tracker || fail "Tracker DEV service inactive"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Release branch moved from pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descended from Release 652"
g show "$TARGET:scripts/tracker-instance-check653.py" |
  "$APP/.venv/bin/python" - --config /etc/tracker.env ||
  fail "DEV identity verification failed; deployment blocked"
DIR="$(mktemp -d /tmp/tracker-coa653-runner.XXXXXXXX)"
cleanup() { rm -f "$DIR/runner.sh"; rmdir "$DIR" || true; }
trap cleanup EXIT
EXPECTED_BLOB="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$DIR/runner.sh"
[[ "$(g hash-object "$DIR/runner.sh")" == "$EXPECTED_BLOB" ]] ||
  fail "Guarded release runner does not match pinned candidate"
bash -n "$DIR/runner.sh"
echo "COA_653_TARGET=$TARGET"
echo "COA_653_TEST_MODE=RELEASE_SPECIFIC_ONLY"
echo "COA_653_DATABASE_MIGRATION=NOT_REQUIRED"
bash "$DIR/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
