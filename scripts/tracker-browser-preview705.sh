#!/usr/bin/env bash
# Release 705: full guarded browser QA against ONE exact source candidate.
# Read-only with respect to installed DEV/PROD: disposable servers and DB only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93
REF=release/705-csrf-dependency-closeout
fail() { echo "RELEASE_705_BROWSER_PREVIEW_ERROR=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail 'One exact 40-character candidate SHA required'
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail 'Run as root systemd worker on tracker-dev'
[[ -x "$PY" && -d "$APP/.git" ]] || fail 'Configured venv/repo unavailable'
cd "$APP"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   -z "$(git status --porcelain)" &&
   "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail 'Clean installed DEV main at Release 704 required'
systemctl is-active --quiet tracker || fail 'Installed DEV service inactive'
# Lock out concurrent deploy/database replication while testing. No live DB reads.
exec 9>/run/lock/tracker-db-sync.lock
flock -n 9 || fail 'Release or database replication lock is held'
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail 'Release 705 branch moved; no unreviewed candidate will run'
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail 'Candidate not descended from installed Release 704'
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    scripts/tracker_dependency_lock705.py|\
    scripts/tracker_csrf_closeout705.py|\
    scripts/tracker_csrf_reconcile627.py|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-browser-preview705.sh|\
    scripts/tracker-release-scoped705.sh|\
    scripts/tracker-preview705.sh|\
    tests/test_release705_combined.py|\
    tests/test_release705_runtime_preview.py|\
    tests/test_csrf_all_registered_negative705.py|\
    tests/test_release627_csrf_reconciliation.py|\
    docs/release-705-csrf-dependency-closeout.md) ;;
    *) fail "Unreviewed path in Release 705: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-browser-preview705.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA"; then
      echo 'RELEASE_705_BROWSER_PREVIEW_ERROR=Worktree cleanup failed' >&2
      status=1
    fi
  fi
  rm -rf -- "$RUN"
  echo "RELEASE_705_BROWSER_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail 'Detached source SHA mismatch'
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
cd "$QA"
bash -n scripts/tracker-browser-qualify.sh
# One invocation revalidates the entire source-only contract for this exact
# candidate SHA before any full browser traffic is generated.
bash scripts/tracker-release-scoped705.sh "$PY"
echo 'RELEASE_705_SOURCE_REVALIDATED=PASSED'
echo 'RELEASE_705_BROWSER_INVENTORY_PREFLIGHT=PASSED'
echo "RELEASE_705_BROWSER_EXECUTED_CANDIDATE=$TARGET"
echo 'RELEASE_705_BROWSER_MODE=FULL_DISPOSABLE_HTTP_HTTPS_STRICT'
# Existing runner owns disposable HTTP and HTTPS proxies, test database,
# 16-worker standard/strict tests, cleanup and error propagation.
timeout --signal=TERM --kill-after=30s 2100 \
  bash scripts/tracker-browser-qualify.sh "$QA" "$PY"
echo 'RELEASE_705_BROWSER_FULL=PASSED_DISPOSABLE_NO_INSTALL'
echo 'RELEASE_705_BROWSER_ISSUE9=BLOCKED_PENDING_POSITIVE_COVERAGE'
echo 'RELEASE_705_DEPENDENCY_ISSUE10=NOT_REPLAYED'
