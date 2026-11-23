#!/usr/bin/env bash
# One-time Release 762 recovery: repair only DEV's stale cached control ref.
# Preserve the audited control-history anchor, source tree, and stage idempotency.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
STATE=/var/lib/tracker-release-agent
LOCAL=refs/remotes/origin/tracker-release-requests
TMP=refs/tracker-release-repair762/candidate
OLD=9571f2ca74974095de1a6dcd35b6d9764f331834
NEW=63945abeccaa93996fef6aa0fa4dabd3223e05a5
ANCHOR=ddcfd3185667cdb273f47c6a3c96fafaf8d8d55d
BASE=04fd141daa17fd2055f9177527296eb9165a59d2
TARGET=35f6aa42aac648f3ed5af527620bd5f4b702b486
REQ=r762-devinstall35f6aa42
g() { git -c "safe.directory=$APP" -C "$APP" "$@"; }
fail() { printf 'TRACKER_762_RECOVERY=BLOCKED: %s\n' "$*" >&2; exit 1; }
[[ $(id -u) == 0 && $(hostname -s) == tracker-dev ]] || fail 'Requires root on tracker-dev'
[[ -d "$APP/.git" && -f "$STATE/control-history745.json" ]] || fail 'Missing repository or control-history anchor'
[[ $(g branch --show-current) == main && $(g rev-parse HEAD) == "$BASE" ]] || fail 'DEV baseline differs'
[[ -z $(g status --porcelain) ]] || fail 'DEV checkout is not clean'
systemctl stop tracker-release-agent.timer || fail 'Cannot pause agent timer'
cleanup() {
  g update-ref -d "$TMP" >/dev/null 2>&1 || true
  systemctl start tracker-release-agent.timer >/dev/null 2>&1 || true
}
trap cleanup EXIT
if systemctl is-active --quiet tracker-release-agent.service; then fail 'Agent already running'; fi
[[ ! -e "$STATE/pending.json" ]] || fail 'Pending unpublished receipt exists'
[[ ! -e "$STATE/$REQ.started" && ! -e "$STATE/r762-dev-install35f6aa42.started" ]] || fail 'Installation may already have begun'
cached=$(g rev-parse "$LOCAL")
[[ "$cached" == "$OLD" ]] || fail "Unexpected locally cached control ref: $cached"
anchor_ref=$(python3 - "$STATE/control-history745.json" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f: print(json.load(f).get('ref',''))
PY
)
[[ "$anchor_ref" == "$ANCHOR" ]] || fail "Unexpected audit anchor: $anchor_ref"
remote=$(g ls-remote origin refs/heads/tracker-release-requests | awk '{print $1}')
[[ "$remote" == "$NEW" ]] || fail "Remote control ref changed: $remote"
g fetch --no-tags origin "refs/heads/tracker-release-requests:$TMP"
[[ $(g rev-parse "$TMP") == "$NEW" ]] || fail 'Fetched candidate mismatch'
g merge-base --is-ancestor "$ANCHOR" "$NEW" || fail 'Audit anchor ancestry mismatch'
[[ $(g rev-list --count "$ANCHOR..$NEW") == 1 ]] || fail 'Unexpected intervening control commits'
python3 - "$NEW" "$REQ" "$BASE" "$TARGET" <<'PY' || fail 'Corrected command mismatch'
import json,subprocess,sys
sha,req,base,target=sys.argv[1:]
raw=subprocess.run(['git','-c','safe.directory=/opt/tracker','-C','/opt/tracker',
                    'show',f'{sha}:control/current.json'],capture_output=True,
                   text=True,check=True).stdout
assert json.loads(raw)=={
 'schema':1,'request_id':req,'action':'dev_install','release':762,
 'target':target,'base':base,'ref':'release/762-body-composition-progress',
 'previous_request_id':'r762-qualify35f6aa42'}
PY
[[ $(g rev-parse "$LOCAL") == "$OLD" ]] || fail 'Cached ref changed during validation'
g update-ref "$LOCAL" "$NEW" "$OLD"
[[ $(g rev-parse "$LOCAL") == "$NEW" ]] || fail 'Cached ref did not update'
echo 'TRACKER_762_CONTROL_REF_RECOVERY=SUCCESS'
echo 'TRACKER_762_DEV_INSTALL=NOT_YET_VERIFIED'
systemctl reset-failed tracker-release-agent.service || true
systemctl start tracker-release-agent.timer
systemctl start --no-block tracker-release-agent.service
echo 'TRACKER_762_AGENT_RETRY=STARTED'
echo 'Verify immutable r762-devinstall35f6aa42 receipt before declaring DEV ready.'
