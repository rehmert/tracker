#!/usr/bin/env bash
# Release 705: two independent offline Python/backend replays in disposable /tmp.
# MUST be run under systemd PrivateNetwork=yes; no downloads or live venv changes.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93
REF=release/705-csrf-dependency-closeout
fail() { echo "DEPENDENCY_705_OFFLINE_REPLAY_ERROR=$*" >&2; exit 1; }

[[ "$#" == 3 && "$1" =~ ^[a-f0-9]{40}$ &&
   "$2" == --execute-disposable &&
   "$3" =~ ^/tmp/tracker705-wheel-acquire[.][A-Za-z0-9_]{8}$ ]] ||
  fail 'Usage: tracker-dependency-replay705.sh EXACT_SHA --execute-disposable RETAINED_WHEEL_ROOT'
TARGET="$1"
WHEEL_ROOT="$3"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail 'Replay requires root systemd worker on tracker-dev'
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail 'PrivateNetwork=yes is required; no network-isolated namespace detected'
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail 'Installed DEV Python or repository unavailable'

cd "$APP"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail 'Installed DEV must be clean pinned Release 704 main'
systemctl is-active --quiet tracker || fail 'Installed DEV service unavailable'
exec 9>/run/lock/tracker705-dependency-preview.lock
flock -n 9 || fail 'Another Release 705 dependency operation is running'
[[ -d "$WHEEL_ROOT/wheelhouse" &&
   -f "$WHEEL_ROOT/receipts/tracker-python-wheels705.json" &&
   -f "$WHEEL_ROOT/receipts/requirements-hashes705.txt" &&
   -f "$WHEEL_ROOT/receipts/pypi-sha256705.json" ]] ||
  fail 'Verified wheelhouse or SHA receipts missing; no download fallback'
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail 'Candidate must already be fetched and pinned; no network fetch allowed'
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail 'Candidate does not descend from installed DEV'
git diff --check "$BASE" "$TARGET"

ALLOWED="$(git show "$TARGET:scripts/tracker-preview705.sh")"
while IFS= read -r path; do
  grep -Fqx "    $path|\\" <<< "$ALLOWED" ||
  grep -Fqx "    $path) ;;" <<< "$ALLOWED" ||
    fail "Unreviewed source path: $path"
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker705-replay-work.XXXXXXXX)"
EVIDENCE="$(mktemp -d /tmp/tracker705-replay-evidence.XXXXXXXX)"
QA="$RUN/candidate"
echo "DEPENDENCY_705_REPLAY_EVIDENCE_ROOT=$EVIDENCE"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA"; then
      status=1
      echo 'DEPENDENCY_705_OFFLINE_REPLAY_ERROR=Worktree cleanup failed' >&2
    fi
  fi
  # Both fresh venvs and synthetic Tracker databases are always removed.
  rm -rf -- "$RUN"
  [[ "$(git -C "$APP" branch --show-current)" == main &&
     "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
     -z "$(git -C "$APP" status --porcelain)" ]] || {
    status=1
    echo 'DEPENDENCY_705_OFFLINE_REPLAY_ERROR=Installed DEV source changed' >&2
  }
  echo 'DEPENDENCY_705_REPLAY_DISPOSABLE_ENVS_REMOVED=YES'
  echo "DEPENDENCY_705_REPLAY_EVIDENCE_RETAINED=$EVIDENCE"
  echo "DEPENDENCY_705_REPLAY_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail 'Detached candidate SHA mismatch'
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
cd "$QA"

# Source-only gate on the exact candidate, before any isolated installation.
bash -n scripts/tracker-dependency-replay705.sh
bash scripts/tracker-release-scoped705.sh "$PY"
echo 'DEPENDENCY_705_REPLAY_SOURCE_GATE=PASSED'

# Audit current installed DEV and wheelhouse without performing any install.
"$PY" -B scripts/tracker_dependency_readiness705.py --wheelhouse "$WHEEL_ROOT/wheelhouse"
echo 'DEPENDENCY_705_REPLAY_INSTALLED_BASELINE_PREFLIGHT=PASSED'

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker_dependency_replay705.py \
    --execute-disposable \
    --source "$QA" --sha "$TARGET" \
    --wheel-root "$WHEEL_ROOT" \
    --runroot "$RUN" --evidence "$EVIDENCE" --base-python "$PY"

echo 'DEPENDENCY_705_REPLAY_PREVIEW=PASSED_DISPOSABLE_NO_DOWNLOAD'
