#!/usr/bin/env bash
# Release 746: concurrent Work-task coordination contract and guarded scoped regressions; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=b7435e55659fbb09819101ebd621aca2c72059c9
REF=release/746-final-hardening-macd-css
fail() { echo "RELEASE_746_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Expected exact candidate SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV source missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed Release 745 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker746-release-coordination.lock
flock -n 9 || fail "Another Release 746 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 746 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 745"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/templates/base.html|\
    app/static/css/tracker-global-density-bundle746.css|\
    tests/test_layout_density685.py|\
    tests/test_compact_spacing686.py|\
    tests/test_shortcuts_toolbar687.py|\
    tests/test_dashboard_polish688.py|\
    tests/test_workout_footnote_spacing689.py|\
    tests/test_workout_footnote_spacing689.py|\
    tests/test_css_consolidation699.py|\
    tests/test_css_consolidation700.py|\
    scripts/tracker_host_evidence746.py|\
    tests/test_release746_hardening.py|\
    tests/test_release746_strict_water.py|\
    scripts/tracker-qualify746.sh|\
    scripts/tracker-install746.sh|\
    scripts/tracker-release-scoped746.sh|\
    docs/release-746-final-hardening.md|\
    docs/tracker-macd-acceptance746.md) ;;
    *) fail "Unexpected Release 746 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker746-release-coordination.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_746_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_746_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_746_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_746_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "QA worktree differs from exact target"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
bash -n scripts/tracker-qualify746.sh
bash -n scripts/tracker-release-scoped746.sh
bash -n scripts/tracker-install746.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped746.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_746_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped746.sh "$PY"
echo "RELEASE_746_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
