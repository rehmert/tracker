#!/usr/bin/env bash
# Release 706: guarded DEV-only issue 9/10 diagnostics and disposable browser replay.
# No network, downloads, live environment modifications, PROD or CSRF activation.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/706-csrf-runtime-and-browser-repro
fail() { echo "RELEASE_706_BLOCKED=$*" >&2; exit 1; }

[[ "$#" == 2 && "$1" =~ ^[a-f0-9]{40}$ &&
   "$2" == /tmp/tracker705-wheel-acquire.u523ry6c ]] ||
  fail "Exact candidate SHA and approved 705 private wheel root required"
TARGET="$1"
WHEELS="$2"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail "Run as root systemd worker on tracker-dev"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Configured source or interpreter missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed DEV Release 705 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker705-dependency-preview.lock
flock -n 9 || fail "Dependency audit or replay already running"
exec 8>/run/lock/tracker706-issue-review.lock
flock -n 8 || fail "Another 706 issue review running"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Exact branch must be fetched before offline worker starts"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate is not descendant of installed 705"
git diff --check "$BASE" "$TARGET"
[[ -d "$WHEELS/wheelhouse" &&
   -f "$WHEELS/receipts/tracker-python-wheels705.json" &&
   -f "$WHEELS/receipts/requirements-hashes705.txt" &&
   -f "$WHEELS/receipts/pypi-sha256705.json" ]] ||
  fail "Approved private 705 wheelhouse/receipts missing"

while IFS= read -r path; do
  case "$path" in
    scripts/tracker_browser_os_replay706.py|\
    scripts/tracker_csrf_survey706.py|\
    scripts/tracker-issue-review706.sh|\
    scripts/tracker-release-scoped706.sh|\
    tests/test_release706_gates.py|\
    docs/release-706-issues9-10.md) ;;
    *) fail "Unreviewed Release 706 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker706-browser-work.XXXXXXXX)"
EVIDENCE="$(mktemp -d /tmp/tracker706-browser-evidence.XXXXXXXX)"
SURVEY="$(mktemp -d /tmp/tracker706-csrf-probe.XXXXXXXX)"
QA="$RUN/candidate"
mkdir -m 700 "$SURVEY/data"
echo "RELEASE_706_EVIDENCE_ROOT=$EVIDENCE"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA"; then
      echo 'RELEASE_706_BLOCKED=Detached worktree cleanup failed' >&2
      status=1
    fi
  fi
  rm -rf -- "$RUN" "$SURVEY"
  [[ "$(git -C "$APP" branch --show-current)" == main &&
     "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
     -z "$(git -C "$APP" status --porcelain)" ]] || {
    echo 'RELEASE_706_BLOCKED=Installed DEV source changed' >&2
    status=1
  }
  echo 'RELEASE_706_INSTALLED_DEV_UNMODIFIED=VERIFIED'
  echo 'RELEASE_706_DISPOSABLE_DIRS_REMOVED=YES'
  echo "RELEASE_706_EVIDENCE_RETAINED=$EVIDENCE"
  echo "RELEASE_706_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Detached candidate SHA mismatch"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
cd "$QA"

# Source regression is limited to issues 9/10; previous source and signed
# coverage is retained by running the historical 705 scope as a dependency.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTHONPATH="$QA" TRACKER_DATA_DIR="$SURVEY/data" \
  PYTHONDONTWRITEBYTECODE=1 \
  bash scripts/tracker-release-scoped706.sh "$PY"
echo 'RELEASE_706_SOURCE_GATE=PASSED'

# Classification evidence, NOT successful business write certification.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTHONPATH="$QA" TRACKER_DATA_DIR="$SURVEY/data" \
  TRACKER_INSTANCE=DEV TRACKER_TEST_ISOLATED=1 TRACKER_CSRF_ENFORCE=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker_csrf_survey706.py \
    --execute-report --output "$EVIDENCE/csrf-survey706.json"
echo 'CSRF_706_SIGNED_REACHABILITY_SURVEY=COMPLETED_NOT_CLEARED'

# Exact locked-wheel replay; no browser download, no remote services.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker_browser_os_replay706.py \
    --execute-disposable --source "$QA" --sha "$TARGET" \
    --wheel-root "$WHEELS" --runroot "$RUN" \
    --evidence "$EVIDENCE" --base-python "$PY"

echo 'RELEASE_706_RUNTIME_EVIDENCE=COMPLETED_NO_DEPLOYMENT'
echo 'RELEASE_706_ISSUE9=BLOCKED_PENDING_SIGNED_SUCCESSFUL_BROWSER_LIFECYCLES'
echo 'RELEASE_706_ISSUE10=BLOCKED_PENDING_INDEPENDENT_ORIGIN_OS_AND_LIVE_ROLLBACK'
