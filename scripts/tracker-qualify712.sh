#!/usr/bin/env bash
# Release 712: only isolated DEV preflight, never deploy/install anything.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=7c662491c3a233b3df60842bbaeaa2dfbc995f06
REF=release/712-u100-syringe-withdraw-units
fail() { echo "RELEASE_712_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 711 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker712-u100-withdraw.lock
flock -n 9 || fail "Another Release 712 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 712 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 711"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/units.py|\
    app/templating.py|\
    app/routers/doses.py|\
    app/blend_dose_unified710.py|\
    app/templates/doses.html|\
    app/templates/dose_edit.html|\
    app/templates/blend_dose_edit711.html|\
    app/templates/_dose_preview.html|\
    app/static/js/tracker-dose-source710.js|\
    docs/release-712-u100-syringe-withdraw-units.md|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-install712.sh|\
    scripts/tracker-qualify712.sh|\
    scripts/tracker-release-scoped712.sh|\
    scripts/tracker-release.sh|\
    tests/browser/test_u100_withdraw712.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release712_u100_withdraw_units.py) ;;
    *) fail "Unexpected Release 712 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker712-u100-withdraw.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_712_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_712_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_712_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_712_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify712.sh
bash -n scripts/tracker-install712.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped712.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_712_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped712.sh "$PY"
echo "RELEASE_712_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
