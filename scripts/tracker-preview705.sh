#!/usr/bin/env bash
# Release 705: exact-SHA source-only candidate QA; no deploy, installs or downloads.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93
REF=release/705-csrf-dependency-closeout
fail() { echo "RELEASE_705_PREVIEW_ERROR=$*" >&2; exit 1; }

[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail 'Run as root systemd worker on tracker-dev'
[[ -x "$PY" && -d "$APP/.git" ]] || fail 'Configured interpreter/repo missing'
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail 'DEV requires clean installed main'
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail 'DEV must be at Release 704'
systemctl is-active --quiet tracker || fail 'DEV service inactive'

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail 'Candidate ancestry mismatch'
git diff --check "$BASE" "$TARGET"

while IFS= read -r path; do
  case "$path" in
    scripts/tracker_dependency_lock705.py|\
    scripts/tracker_csrf_closeout705.py|\
    scripts/tracker_csrf_reconcile627.py|\
    scripts/tracker-browser-qualify.sh|\
    tests/browser/test_vitals_proxy_host522.py|\
    tests/browser/test_strict_csrf521.py|\
    scripts/tracker-browser-preview705.sh|\
    scripts/tracker-release-scoped705.sh|\
    scripts/tracker-preview705.sh|\
    tests/test_release705_combined.py|\
    tests/test_release705_runtime_preview.py|\
    tests/test_csrf_all_registered_negative705.py|\
    tests/test_release627_csrf_reconciliation.py|\
    docs/release-705-csrf-dependency-closeout.md) ;;
    *) fail "Out-of-scope path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview705.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$RUN"
  echo "RELEASE_705_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
cd "$QA"
bash scripts/tracker-release-scoped705.sh "$PY"
echo "RELEASE_705_PREVIEW_QUALIFIED=$TARGET"
echo 'RELEASE_705_PREVIEW=PASSED_ISOLATED_NO_INSTALL'
