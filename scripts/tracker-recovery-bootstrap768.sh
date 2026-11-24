#!/usr/bin/env bash
# Release 768 ONE-TIME controller recovery bootstrap on tracker-dev only.
# Does not install application, touch PROD files, authorize promotion,
# change GitHub control/receipts, or retry the failed 767 stage.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/768-prod-relative-data-path-recovery
DEV=5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13
PROD=8c67580611fd945d9ae83f8015f071a24ab6fee5
FAILED=r767-deploy5d23aaf4
AGENT=/usr/local/sbin/tracker-release-agent.py
STATE=/var/lib/tracker-release-agent
PY=$APP/.venv/bin/python
fail(){ echo "RELEASE_768_BOOTSTRAP_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Provide pinned recovery commit"
TARGET=$1
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
[[ -x "$PY" && -d "$APP/.git" && -d "$STATE" ]] || fail "DEV controller unavailable"
[[ ! -L "$AGENT" && -f "$AGENT" &&
   "$(stat -c '%u:%a' "$AGENT")" == 0:700 ]] ||
  fail "Unexpected privileged installed release-agent identity"
[[ "$(systemctl show -p Type --value tracker-release-agent.service)" == oneshot ]] ||
  fail "Unexpected controller service type"
systemctl show -p ExecStart --value tracker-release-agent.service |
  grep -Fq "$AGENT" || fail "Controller service does not execute pinned agent"
systemctl is-active --quiet tracker.service || fail "DEV Tracker inactive"
exec 9>"$STATE/lock"
flock -n 9 || fail "Controller running; safe retry only after it finishes"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$DEV" &&
   -z "$(git status --porcelain)" ]] ||
  fail "DEV installed source does not match verified Release 767"
git fetch --no-tags origin \
  "refs/heads/$REF:refs/remotes/origin/$REF" \
  "refs/heads/tracker-release-requests:refs/remotes/origin/tracker-release-requests" \
  "refs/heads/tracker-release-receipts:refs/remotes/origin/tracker-release-receipts" \
  "refs/heads/main:refs/remotes/origin/main"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" &&
   "$(git rev-parse refs/remotes/origin/main)" == "$DEV" ]] ||
  fail "Recovery branch or main drift"
git merge-base --is-ancestor "$DEV" "$TARGET" ||
  fail "Recovery is not a descendant of the installed DEV SHA"
# No application behavior may differ from the previously qualified Release 766.
while IFS= read -r filename; do
 case "$filename" in
  scripts/*|tests/*|docs/*) ;;
  *) fail "Unreviewed app/data diff: $filename" ;;
 esac
done < <(git diff --name-only "$DEV" "$TARGET")
# Verify the old installed agent is the exact source from the failed release,
# and the queue still has the single immutable failed PROD receipt.
[[ "$(git hash-object "$AGENT")" ==
   "$(git rev-parse "$DEV:scripts/tracker-release-agent745.py")" ]] ||
  fail "Host agent differs from known installed source"
"$PY" -B - "$FAILED" "$DEV" "$PROD" <<'PYCODE'
import json, subprocess, sys
req, dev, prod = sys.argv[1:]
def read(ref, path):
    return json.loads(subprocess.check_output(
        ["git", "show", f"{ref}:{path}"], text=True
    ))
control = read("refs/remotes/origin/tracker-release-requests","control/current.json")
latest = read("refs/remotes/origin/tracker-release-receipts","receipts/latest.json")
immutable = read("refs/remotes/origin/tracker-release-receipts",f"receipts/{req}.json")
assert latest == immutable and control["request_id"] == req
assert control["action"] == "prod_deploy" and control["target"] == dev
assert immutable["status"] == "failed" and immutable["exit_code"] == 1
assert immutable["failure_category"] == "PromotionOrDeploymentGate"
assert immutable["base"] == prod and immutable["target"] == dev
assert "PROMOTED_COMMIT="+dev in immutable["markers"]
assert "REMOTE_DEPLOY_EXIT_STATUS=1" in immutable["markers"]
print("RELEASE_768_FAILED_RECEIPT=IMMUTABLY_VERIFIED")
PYCODE
REMOTE_HEAD="$(ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes \
 -n root@tracker-prod \
 'test "$(hostname -s)" = tracker-prod && git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')" ||
 fail "Cannot independently read PROD installed code"
[[ "$REMOTE_HEAD" == "$PROD" ]] || fail "PROD has changed; no bootstrap"
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes \
 -n root@tracker-prod 'systemctl is-active --quiet tracker' ||
 fail "PROD Tracker inactive; no bootstrap"
echo "RELEASE_768_PROD_STILL_765=VERIFIED"
STAGE="$(mktemp -d /tmp/tracker768-bootstrap.XXXXXXXX)"
WORK="$STAGE/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$WORK" ]]; then git worktree remove --force "$WORK" || rc=1; fi
 rm -rf -- "$STAGE"
 exit "$rc"
}
trap cleanup EXIT
git worktree add --detach "$WORK" "$TARGET"
[[ "$(git -C "$WORK" rev-parse HEAD)" == "$TARGET" ]] ||
 fail "Staged recovery source mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$WORK"
mkdir -m 0700 "$STAGE/data"
(
 cd "$WORK"
 export PYTHONPATH="$WORK" TRACKER_DATA_DIR="$STAGE/data"
 export PYTHONDONTWRITEBYTECODE=1
 "$PY" -B -m pytest -q --tb=short --disable-warnings \
   tests/test_release768_recovery.py tests/test_release745_controller.py \
   tests/test_release767_prod_schema_backup.py ||
   fail "New controller or path guard regression"
 bash -n scripts/tracker-recovery-bootstrap768.sh
 "$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
for p in ("scripts/tracker-release-agent745.py",
          "scripts/tracker-promote568.py",
          "scripts/tracker-prod-schema-backup767.py"):
    if not Path(p).is_file():
        if "tracker-promote568" in p:
            p="scripts/tracker_promote568.py"
    ast.parse(Path(p).read_text(), filename=p)
print("RELEASE_768_BOOTSTRAP_SOURCE=VALIDATED")
PYCODE
)
# This is the only privileged local change: atomic replacement of the host
# controller with the pinned, tested code. The current failed receipt remains
# immutable; a subsequent NEW request will still need qualification.
PREVIOUS="$STATE/agent-before768.py"
[[ ! -e "$PREVIOUS" && ! -L "$PREVIOUS" ]] ||
 fail "Controller bootstrap already attempted; do not repeat"
install -o root -g root -m 0700 "$AGENT" "$PREVIOUS"
NEW="$STATE/.agent768.$$.new"
[[ ! -e "$NEW" && ! -L "$NEW" ]] || fail "Staged agent exists"
install -o root -g root -m 0700 \
  "$WORK/scripts/tracker-release-agent745.py" "$NEW"
[[ "$(git hash-object "$NEW")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
 fail "Staged controller hash differs from qualified SHA"
mv -f "$NEW" "$AGENT"
[[ "$(stat -c '%u:%a' "$AGENT")" == 0:700 &&
   "$(git hash-object "$AGENT")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
 fail "Installed controller verification failed"
echo "RELEASE_768_CONTROLLER_RECOVERY_BOOTSTRAP=SUCCESS"
echo "RELEASE_768_PROD=UNCHANGED"
echo "RELEASE_767_FAILED_RECEIPT=RETAINED"
