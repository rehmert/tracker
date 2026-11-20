#!/usr/bin/env bash
# One-time, DEV-only installation. Does not deploy Tracker or issue a release.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=ops/tracker-release-control
fail() { echo "TRACKER_RELEASE_AGENT_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail 'Exact pinned code commit required'
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail 'root on tracker-dev only'
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail 'Installed DEV must be clean main'
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail 'Tracker environment missing'
systemctl is-active --quiet tracker || fail 'Tracker service must be active'
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail 'Ops branch has changed'
STAGE="$(mktemp -d /tmp/tracker-agent-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
for name in tracker-release-agent.py tracker-release-agent-install.sh; do
  rel="scripts/$name"
  git show "$TARGET:$rel" > "$STAGE/$name"
  [[ "$(git hash-object "$STAGE/$name")" == "$(git rev-parse "$TARGET:$rel")" ]] || fail "Object mismatch: $rel"
done
python3 -m py_compile "$STAGE/tracker-release-agent.py"
bash -n "$STAGE/tracker-release-agent-install.sh"
# Ensure local tree is identical to the pinned source before installing the agent.
[[ "$(git hash-object "$STAGE/tracker-release-agent-install.sh")" == "$(git hash-object "$0")" ]] || fail 'Installer code not pinned'
install -d -o root -g root -m 700 /var/lib/tracker-release-agent
install -d -o root -g root -m 700 /var/log/tracker-release-agent
install -o root -g root -m 700 "$STAGE/tracker-release-agent.py" /usr/local/sbin/tracker-release-agent.py
cat > /etc/systemd/system/tracker-release-agent.service <<'UNIT'
[Unit]
Description=Tracker release control (one pinned stage per GitHub command)
After=network-online.target
Wants=network-online.target
ConditionPathExists=/opt/tracker/.git
[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/tracker
ExecStart=/usr/bin/python3 -I /usr/local/sbin/tracker-release-agent.py
TimeoutStartSec=55min
UMask=0077
UNIT
cat > /etc/systemd/system/tracker-release-agent.timer <<'TIMER'
[Unit]
Description=Check for an approved next Tracker release step
[Timer]
OnBootSec=1min
OnUnitInactiveSec=45s
AccuracySec=5s
RandomizedDelaySec=0
Unit=tracker-release-agent.service
[Install]
WantedBy=timers.target
TIMER
chmod 644 /etc/systemd/system/tracker-release-agent.service /etc/systemd/system/tracker-release-agent.timer
systemctl daemon-reload
systemctl enable --now tracker-release-agent.timer
systemctl is-enabled --quiet tracker-release-agent.timer || fail 'Timer did not enable'
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail 'Unexpected installed source change'
echo 'TRACKER_RELEASE_AGENT_INSTALL=SUCCESS'
echo "TRACKER_RELEASE_AGENT_PINNED_COMMIT=$TARGET"
echo 'TRACKER_RELEASE_AGENT_TIMER=ENABLED'
echo 'TRACKER_RELEASE_AGENT_PROD=UNTOUCHED'
