#!/usr/bin/env bash
# Release 705: explicitly authorized download-only pinned wheel acquisition.
# DEV root/systemd, immutable candidate, private retained /tmp receipts.
# No pip installs, venv changes, browser downloads or DEV/PROD deployments.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93
REF=release/705-csrf-dependency-closeout
fail() { echo "DEPENDENCY_705_ACQUIRE_ERROR=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail 'Exactly one approved 40-character candidate SHA required'
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail 'Run as root systemd worker on tracker-dev'
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail 'Installed Python/repository unavailable'
cd "$APP"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail 'Installed DEV must be clean Release 704 main'
systemctl is-active --quiet tracker || fail 'Installed DEV service inactive'
# Serialize acquisition with the existing read-only dependency audit.
exec 9>/run/lock/tracker705-dependency-preview.lock
flock -n 9 || fail 'Another Release 705 dependency operation is active'
[[ "$(df -B1 --output=avail /tmp | tail -1)" -ge 1073741824 ]] ||
  fail 'Under 1 GiB free in /tmp; do not begin downloads'

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail 'Candidate branch moved or SHA mismatch'
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail 'Candidate not descended from installed Release 704'
git diff --check "$BASE" "$TARGET"

# Match every changed file against the exact candidate's guarded Release
# 705 allowlist before executing code from the detached worktree.
ALLOWED="$(git show "$TARGET:scripts/tracker-preview705.sh")"
while IFS= read -r path; do
  grep -Fqx "    $path|\\" <<< "$ALLOWED" ||
  grep -Fqx "    $path) ;;" <<< "$ALLOWED" ||
    fail "Unreviewed candidate path: $path"
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker705-acquisition-preview.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA"; then
      status=1
      echo 'DEPENDENCY_705_ACQUIRE_ERROR=Worktree cleanup failed' >&2
    fi
  fi
  rm -rf -- "$RUN"
  echo "DEPENDENCY_705_ACQUIRE_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail 'Detached source SHA mismatch'
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
cd "$QA"

bash -n scripts/tracker-dependency-acquire705.sh
bash scripts/tracker-release-scoped705.sh "$PY"
echo 'DEPENDENCY_705_ACQUIRE_SOURCE_GATE=PASSED'
echo "DEPENDENCY_705_ACQUIRE_CANDIDATE=$TARGET"
# Read-only baseline audit must pass before any network downloads.
"$PY" -B scripts/tracker_dependency_readiness705.py
echo 'DEPENDENCY_705_ACQUIRE_BASELINE_PREFLIGHT=PASSED'
# Script is opt-in, downloads only wheels from HTTPS PyPI into separate
# private /tmp storage. Retain wheelhouse and receipts independently
# of the ephemeral source worktree even when acquisition fails.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker_dependency_acquire705.py --execute-download

[[ "$(git -C "$APP" branch --show-current)" == main &&
   "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
   -z "$(git -C "$APP" status --porcelain)" ]] ||
  fail 'Installed DEV source changed during acquisition'
echo 'DEPENDENCY_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED'
echo 'DEPENDENCY_705_ACQUIRE_PREVIEW=PASSED_NO_INSTALL'
