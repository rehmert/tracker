#!/usr/bin/env bash
# Release 745 guarded source-only release coordination DEV install; exact qualified SHA only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=0e9925532127eab2c939fb4ed5c045c6bf0dbe11
REF=release/745-macd-mobile-controller
fail() { echo "RELEASE_745_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Supply qualified exact commit SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Must run as root on tracker-dev"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] ||
  fail "Tracker environment unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Unexpected DEV source or dirty tree"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not fast-forward"
STAGE="$(mktemp -d /tmp/tracker745-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
EXPECTED_BLOB="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
ACTUAL_BLOB="$(git hash-object "$RUNNER")"
[[ "$ACTUAL_BLOB" == "$EXPECTED_BLOB" ]] ||
  fail "Runner Git blob mismatch"
bash -n "$RUNNER"
# Verify the installed DEV agent against its reviewed ops source before promotion.
TRUSTED_AGENT=34e78e401ef1ea7d7bc3b268469197cecb803ebc
git fetch origin "refs/heads/ops/tracker-release-control:refs/remotes/origin/ops/tracker-release-control"
[[ "$(git rev-parse refs/remotes/origin/ops/tracker-release-control)" == "$TRUSTED_AGENT" ]] ||
  fail "Ops agent source moved: needs independent review"
INSTALLED_AGENT=/usr/local/sbin/tracker-release-agent.py
[[ -f "$INSTALLED_AGENT" && ! -L "$INSTALLED_AGENT" &&
   "$(stat -c '%u:%a' "$INSTALLED_AGENT")" == "0:700" ]] ||
  fail "Installed host agent has unsafe identity or permissions"
[[ "$(git hash-object "$INSTALLED_AGENT")" ==
   "$(git rev-parse "$TRUSTED_AGENT:scripts/tracker-release-agent.py")" ]] ||
  fail "Host agent is not the reviewed Release 744 baseline"
AGENT="$STAGE/tracker-release-agent745.py"
git show "$TARGET:scripts/tracker-release-agent745.py" > "$AGENT"
[[ "$(git hash-object "$AGENT")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
  fail "Pinned agent Git object mismatch"
"$APP/.venv/bin/python" -B -m py_compile "$AGENT" ||
  fail "Pinned agent Python compilation failed"
echo "RELEASE_745_HOST_AGENT_PREFLIGHT=PASSED"

echo "RELEASE_745_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" &&
     -z "$(git -C "$APP" status --porcelain)" ]] ||
  fail "App DEV installation did not finish cleanly"
# The running Python service keeps its in-memory old agent until this stage
# publishes a receipt. The next timer cycle loads the atomically replaced file.
BACKUP=/var/lib/tracker-release-agent/agent-before745.py
[[ ! -e "$BACKUP" && ! -L "$BACKUP" ]] ||
  fail "Agent upgrade already attempted; require manual reconciliation"
install -m 0700 -o root -g root "$INSTALLED_AGENT" "$BACKUP"
STAGED_AGENT=/usr/local/sbin/.tracker-release-agent745.new
[[ ! -e "$STAGED_AGENT" && ! -L "$STAGED_AGENT" ]] ||
  fail "Agent stage file already exists"
install -m 0700 -o root -g root "$AGENT" "$STAGED_AGENT"
[[ "$(git hash-object "$STAGED_AGENT")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
  fail "Stage agent object mismatch"
mv -f "$STAGED_AGENT" "$INSTALLED_AGENT"
[[ -f "$INSTALLED_AGENT" && ! -L "$INSTALLED_AGENT" &&
   "$(stat -c '%u:%a' "$INSTALLED_AGENT")" == "0:700" &&
   "$(git hash-object "$INSTALLED_AGENT")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
  fail "Host agent installation integrity mismatch"
echo "RELEASE_745_HOST_AGENT_INSTALLED=VERIFIED"
echo "RELEASE_745_DEV_INSTALL=SUCCESS"
