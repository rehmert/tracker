#!/usr/bin/env bash
# Release 732: isolated, audited medication hard-delete qualification; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=0bc005f9c1e5b1353a67755aeeb2940140a7c74f
REF=release/732-medication-delete
fail() { echo "RELEASE_732_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 731 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker732-medication-delete.lock
flock -n 9 || fail "Another Release 732 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 732 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 731"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/regimen635.py|\
    app/templates/regimen635.html|\
    docs/release-732-medication-delete.md|\
    scripts/tracker-install732.sh|\
    scripts/tracker-qualify732.sh|\
    scripts/tracker-release-scoped732.sh|\
    tests/test_release732_medication_delete.py) ;;
    *) fail "Unexpected Release 732 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker732-medication-delete.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_732_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_732_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_732_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_732_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify732.sh
bash -n scripts/tracker-release-scoped732.sh
bash -n scripts/tracker-install732.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped732.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_732_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped732.sh "$PY"
echo "RELEASE_732_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
