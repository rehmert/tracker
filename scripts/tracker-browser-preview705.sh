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

[[ "$#" -ge 1 && "$#" -le 2 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail 'Exact candidate SHA and optional approved targeted mode required'
TARGET="$1"
PREVIEW_MODE=full
if [[ "$#" == 2 ]]; then
  case "$2" in
    --targeted-workflows580) PREVIEW_MODE=workflows580 ;;
    --targeted-preparations583) PREVIEW_MODE=preparations583 ;;
    *) fail 'Only approved 580/583 targeted modes are supported' ;;
  esac
fi
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
# The test server/database are disposable; routine live database replication
# must not block browser QA. Serialize only other Release 705 browser previews.
exec 9>/run/lock/tracker705-browser-preview.lock
flock -n 9 || fail 'Another Release 705 full browser preview is active'
echo 'RELEASE_705_DB_SYNC_LOCK=NOT_ACQUIRED_DISPOSABLE_ONLY'
# The browser runner reads one installed vendor asset into the isolated
# worktree. Verify it is unchanged after QA and never accept a live checkout
# drift as valid candidate evidence.
VENDOR=/opt/tracker/app/static/vendor/htmx.min.js
[[ -f "$VENDOR" && ! -L "$VENDOR" ]] ||
  fail 'Trusted installed HTMX asset unavailable'
VENDOR_SHA_BEFORE="$(sha256sum "$VENDOR" | awk '{print $1}')"
[[ "$VENDOR_SHA_BEFORE" =~ ^[0-9a-f]{64}$ ]] ||
  fail 'Trusted vendor asset fingerprint unavailable'
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
    scripts/tracker_csrf_runtime_report579.py|\
    tests/test_release579_csrf_runtime_report.py|\
    tests/test_release575_csrf_js_review.py|\
    tests/test_release576_csrf_js_triage.py|\
    tests/test_release578_csrf_route_ledger.py|\
    tests/test_release640_csrf_inventory.py|\
    tests/test_release648_prod_recovery.py|\
    tests/test_coa_multiple_test_types651.py|\
    scripts/tracker-browser-qualify.sh|\
    tests/browser/test_vitals_proxy_host522.py|\
    tests/browser/test_strict_csrf521.py|\
    tests/browser/test_csrf_workflows580.py|\
    tests/browser/test_csrf_preparations583.py|\
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
if [[ "$PREVIEW_MODE" == workflows580 ]]; then
  echo 'RELEASE_705_MODE=TARGETED_WORKFLOWS580_NOT_FULL_QUALIFICATION'
  timeout --signal=TERM --kill-after=30s 420 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict workflows580
  echo 'RELEASE_705_TARGETED_WORKFLOWS580=PASSED_NOT_FULL_QA'
elif [[ "$PREVIEW_MODE" == preparations583 ]]; then
  echo 'RELEASE_705_MODE=TARGETED_PREPARATIONS583_NOT_FULL_QUALIFICATION'
  timeout --signal=TERM --kill-after=30s 420 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
      --targeted-strict tests/browser/test_csrf_preparations583.py
  echo 'RELEASE_705_TARGETED_PREPARATIONS583=PASSED_NOT_FULL_QA'
else
  # Source-qualified candidate only. Each targeted preflight must pass
  # independently before the complete 16-worker suite is attempted.
  echo '=== RELEASE 705 STRICT QUICK ENTRY TARGETED PREFLIGHT ==='
  timeout --signal=TERM --kill-after=30s 300 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict quick603
  echo 'RELEASE_705_TARGETED_QUICK603=PASSED_NOT_FULL_QA'
  echo '=== RELEASE 705 STRICT WORKFLOWS580 TARGETED PREFLIGHT ==='
  timeout --signal=TERM --kill-after=30s 420 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict workflows580
  echo 'RELEASE_705_TARGETED_WORKFLOWS580=PASSED_NOT_FULL_QA'
  echo '=== RELEASE 705 STRICT PREPARATIONS583 TARGETED PREFLIGHT ==='
  timeout --signal=TERM --kill-after=30s 420 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
      --targeted-strict tests/browser/test_csrf_preparations583.py
  echo 'RELEASE_705_TARGETED_PREPARATIONS583=PASSED_NOT_FULL_QA'
  # Existing runner owns the disposable HTTP/HTTPS servers and DB,
  # complete 16-worker browser gates and fail-closed evidence reports.
  timeout --signal=TERM --kill-after=30s 2100 \
    bash scripts/tracker-browser-qualify.sh "$QA" "$PY"
fi
[[ "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
   "$(git -C "$APP" branch --show-current)" == main &&
   -z "$(git -C "$APP" status --porcelain)" ]] ||
  fail 'Installed DEV checkout changed during isolated browser qualification'
[[ -f "$VENDOR" && ! -L "$VENDOR" &&
   "$(sha256sum "$VENDOR" | awk '{print $1}')" == "$VENDOR_SHA_BEFORE" ]] ||
  fail 'Installed HTMX asset changed during isolated browser qualification'
echo 'RELEASE_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED'
if [[ "$PREVIEW_MODE" == workflows580 ]]; then
  echo 'RELEASE_705_TARGETED_WORKFLOWS580_PREVIEW=PASSED_ISOLATED_NO_FULL_QA'
  exit 0
elif [[ "$PREVIEW_MODE" == preparations583 ]]; then
  echo 'RELEASE_705_TARGETED_PREPARATIONS583_PREVIEW=PASSED_ISOLATED_NO_FULL_QA'
  exit 0
fi
echo 'RELEASE_705_BROWSER_FULL=PASSED_DISPOSABLE_NO_INSTALL'
echo 'RELEASE_705_BROWSER_ISSUE9=BLOCKED_PENDING_POSITIVE_COVERAGE'
echo 'RELEASE_705_DEPENDENCY_ISSUE10=NOT_REPLAYED'
