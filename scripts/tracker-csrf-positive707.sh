#!/usr/bin/env bash
# Release 707: twelve real persisted CSRF writes; DEV-only, no deployment.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/707-csrf-positive-lifecycles
fail() { echo "RELEASE_707_BLOCKED=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Exactly one 40-character candidate SHA required"
TARGET="$1"

[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail "DEV systemd/root required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes is required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "DEV Python/repo unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"

[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean Release 705 main required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker707-positive-csrf.lock
flock -n 9 || fail "Another strict-CSRF 707 acceptance is running"

[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release branch not fetched to approved exact SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Unapproved ancestry"
git diff --check "$BASE" "$TARGET"

# Exactly the reviewed docs + tests + browser runner + guarded preview.
while IFS= read -r path; do
  case "$path" in
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-csrf-positive707.sh|\
    tests/browser/test_csrf_regimen_catalog707.py|\
    tests/browser/test_csrf_workout_lifecycles707.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release707_csrf_positive.py|\
    docs/release-707-csrf-positive.md) ;;
    *) fail "Unapproved path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker707-csrf-preview.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA"; then
      echo "RELEASE_707_BLOCKED=Candidate worktree cleanup failed" >&2
      status=1
    fi
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_707_BLOCKED=Installed DEV unexpectedly changed" >&2
    status=1
  fi
  echo "RELEASE_707_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_707_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Detached source mismatch"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export PYTHONPATH="$QA"
export TRACKER_DATA_DIR="$RUN/data"
export PYTHONDONTWRITEBYTECODE=1

bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-csrf-positive707.sh
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release707_csrf_positive.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_707_SOURCE=PASSED"

# Full 16-worker browser startup is reused but only this NEW module executes
# under real strict CSRF. Both HTTP and HTTPS must persist valid mutations.
bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
  --targeted-strict csrf-positive707

echo "RELEASE_707_TARGETED_POSITIVE=PASSED_NOT_GLOBAL_CLEARANCE"
echo "RELEASE_707_VALIDATED_SIGNED_ROUTE_COUNT=29"
echo "RELEASE_707_UNMAPPED_HISTORICAL_ROUTE_GAPS=92_NOT_YET_RECONCILED"
echo "RELEASE_707_GLOBAL_CSRF=BLOCKED_PENDING_OTHER_REAL_WRITES"
