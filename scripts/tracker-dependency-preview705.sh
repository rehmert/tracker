#!/usr/bin/env bash
# Release 705: exact-SHA, read-only DEV dependency readiness audit.
# Never installs, downloads, replays, alters the venv, database or service.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
REF=release/705-csrf-dependency-closeout
BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93
fail() { echo "DEPENDENCY_705_PREVIEW_ERROR=$*" >&2; exit 1; }

[[ "$#" == 1 || "$#" == 3 ]] ||
  fail 'Usage: dependency-preview705.sh EXACT_SHA [--wheelhouse /tmp/PRIVATE]'
[[ "$1" =~ ^[a-f0-9]{40}$ ]] || fail 'Exact 40-character candidate SHA required'
TARGET="$1"
AUDIT_ARGS=()
if [[ "$#" == 3 ]]; then
  [[ "$2" == --wheelhouse && "$3" == /tmp/* ]] ||
    fail 'Only an explicit private /tmp wheelhouse may be read'
  AUDIT_ARGS=(--wheelhouse "$3")
fi

[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail 'Requires root systemd worker on tracker-dev'
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail 'Installed DEV checkout or interpreter missing'
cd "$APP"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail 'Installed DEV must be clean Release 704 main'
systemctl is-active --quiet tracker || fail 'Installed DEV service unavailable'
exec 9>/run/lock/tracker705-dependency-preview.lock
flock -n 9 || fail 'Another dependency readiness audit is active'

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail 'Candidate branch moved'
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail 'Candidate is not descended from installed DEV'
git diff --check "$BASE" "$TARGET"

# Use the release's source preview allowlist, but never execute that
# preview against installed data. Every changed path must be approved.
ALLOWED="$(git show "$TARGET:scripts/tracker-preview705.sh")"
while IFS= read -r path; do
  grep -Fqx "    $path|\\" <<< "$ALLOWED" ||
  grep -Fqx "    $path) ;;" <<< "$ALLOWED" ||
    fail "Unapproved source path: $path"
done < <(git diff --name-only "$BASE" "$TARGET")

ROOT="$(mktemp -d /tmp/tracker705-dependency.XXXXXXXX)"
QA="$ROOT/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    if ! git -C "$APP" worktree remove --force "$QA" >/dev/null; then
      status=1
      echo 'DEPENDENCY_705_PREVIEW_ERROR=Worktree cleanup failed' >&2
    fi
  fi
  rm -rf -- "$ROOT"
  echo "DEPENDENCY_705_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail 'Isolated source mismatch'
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$ROOT/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$ROOT/test-data"
cd "$QA"
bash -n scripts/tracker-dependency-preview705.sh
bash scripts/tracker-release-scoped705.sh "$PY"
echo 'DEPENDENCY_705_SOURCE_REVALIDATED=PASSED'
echo "DEPENDENCY_705_AUDITED_CANDIDATE=$TARGET"
"$PY" -B scripts/tracker_dependency_readiness705.py "${AUDIT_ARGS[@]}"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
   "$(git -C "$APP" branch --show-current)" == main &&
   -z "$(git -C "$APP" status --porcelain)" ]] ||
  fail 'Installed DEV changed during read-only audit'
echo 'DEPENDENCY_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED'
echo 'DEPENDENCY_705_AUDIT=COMPLETED_NO_INSTALL'
