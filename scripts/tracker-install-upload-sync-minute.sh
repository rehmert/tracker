#!/usr/bin/env bash
# Install/enable a DEV-only minute timer for existing Release 645 additive upload sync.
# Installs systemd units outside the application checkout; never alters the DB.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
SERVICE=tracker-upload-sync-dev.service
TIMER=tracker-upload-sync-dev.timer
fail() { echo "UPLOAD_SYNC_SETUP=FAILED: $*" >&2; exit 1; }
[[ $# == 1 && -d "$1" ]] || fail "Staged unit directory required"
STAGE="$(realpath -e -- "$1")"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Installation is allowed only as root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV application checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "Expected Release 689 installed on DEV"
[[ -x "$APP/.venv/bin/python" ]] || fail "Missing configured Python interpreter"
"$APP/.venv/bin/python" scripts/tracker-instance-check653.py --config /etc/tracker.env ||
  fail "DEV identity check failed"
[[ -f scripts/tracker-prod-uploads-to-dev645.sh ]] ||
  fail "Existing additive upload reconciliation script is missing"
bash -n scripts/tracker-prod-uploads-to-dev645.sh
for dep in rsync ssh systemctl systemd-analyze install cmp; do
  command -v "$dep" >/dev/null || fail "Missing requirement: $dep"
done
for unit in "$SERVICE" "$TIMER"; do
  [[ -f "$STAGE/$unit" && ! -L "$STAGE/$unit" ]] ||
    fail "Missing or symlinked staged unit: $unit"
done
systemd-analyze verify "$STAGE/$SERVICE" "$STAGE/$TIMER" ||
  fail "systemd unit verification failed"
ssh -n -T -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes \
  root@tracker-prod 'test "$(hostname -s)" = tracker-prod' ||
  fail "Existing trusted read-only PROD SSH connection unavailable"
echo "UPLOAD_SYNC_REMOTE_HOST=PROD_VERIFIED"
for unit in "$SERVICE" "$TIMER"; do
  destination="/etc/systemd/system/$unit"
  if [[ -e "$destination" || -L "$destination" ]]; then
    [[ -f "$destination" && ! -L "$destination" ]] ||
      fail "Refuse to replace nonregular existing unit: $unit"
    cmp -s "$STAGE/$unit" "$destination" ||
      fail "Refuse to overwrite existing, nonmatching unit: $unit"
    echo "UPLOAD_SYNC_UNIT_ALREADY_CURRENT=$unit"
  else
    install -o root -g root -m 0644 "$STAGE/$unit" "$destination"
    echo "UPLOAD_SYNC_UNIT_INSTALLED=$unit"
  fi
done
systemctl daemon-reload
systemctl enable --now "$TIMER"
systemctl is-active --quiet "$TIMER" || fail "Minute timer not active"
echo "UPLOAD_SYNC_TIMER=ENABLED_ACTIVE"
echo "UPLOAD_SYNC_SCHEDULE=EVERY_CALENDAR_MINUTE"
# Initial reconciliation also runs detached; the systemd timer never overlaps a busy service.
systemctl start --no-block "$SERVICE"
echo "UPLOAD_SYNC_INITIAL_RUN=STARTED_NOT_YET_VERIFIED"
echo "UPLOAD_SYNC_DIRECTION=PROD_TO_DEV_ONLY"
echo "UPLOAD_SYNC_DATABASE=NOT_COPIED"
echo "UPLOAD_SYNC_EXISTING_DEV_FILES=NOT_OVERWRITTEN"
echo "UPLOAD_SYNC_DELETIONS=NONE"
echo "UPLOAD_SYNC_STATUS_COMMAND=systemctl list-timers --all $TIMER"
echo "UPLOAD_SYNC_JOURNAL_COMMAND=journalctl --no-pager -u $SERVICE -n 100 -o cat"
