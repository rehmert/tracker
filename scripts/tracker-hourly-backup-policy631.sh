#!/usr/bin/env bash
# Apply hourly verified Tracker backups with 48-archive retention.
# Explicit operator action on each host; never restarts tracker or deletes files.
set -Eeuo pipefail
umask 077
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

MODE="${1:---audit}"
[[ $# -le 1 && ( "$MODE" == --audit || "$MODE" == --apply ) ]] ||
  fail "Usage: bash tracker-hourly-backup-policy631.sh [--audit|--apply]"
[[ $(id -u) == 0 ]] || fail "Run as root"
case "$(hostname -s)" in tracker-dev|tracker-prod) ;; *) fail "Unexpected host" ;; esac

systemctl cat tracker-backup.timer >/dev/null 2>&1 ||
  fail "tracker-backup.timer missing"
systemctl cat tracker-backup.service >/dev/null 2>&1 ||
  fail "tracker-backup.service missing"
systemctl is-active --quiet tracker-backup.timer ||
  fail "Backup timer not active"
systemctl is-enabled --quiet tracker-backup.timer ||
  fail "Backup timer not enabled"

TRIGGERS="$(systemctl show tracker-backup.service --property=TriggeredBy --value)"
[[ "$TRIGGERS" == tracker-backup.timer ]] ||
  fail "Unexpected backup service triggers: $TRIGGERS; review before changing schedule"

SERVICE="$(systemctl cat tracker-backup.service)"
[[ "$SERVICE" == *'ExecStart=/opt/tracker/.venv/bin/python -m scripts.tracker_backup create'* ]] ||
  fail "Backup service command differs from expected tracked command"

# An additional scheduled path could continue making five-minute copies
# after the canonical timer changes. Refuse to modify anything in that case.
CRON_HITS="$(grep -R -l -E 'scripts[.]tracker_backup|tracker-backup[.]service' \
  /etc/crontab /etc/cron.d /etc/cron.hourly /etc/cron.daily \
  /etc/cron.weekly /etc/cron.monthly 2>/dev/null || true)"
[[ -z "$CRON_HITS" ]] ||
  fail "Other backup scheduler found in cron: $CRON_HITS"

TIMER_DROP=/etc/systemd/system/tracker-backup.timer.d/60-hourly631.conf
SERVICE_DROP=/etc/systemd/system/tracker-backup.service.d/60-retention631.conf
TIMER_TEXT='[Timer]
OnCalendar=
OnBootSec=
OnActiveSec=
OnUnitActiveSec=
OnUnitInactiveSec=
OnCalendar=hourly
RandomizedDelaySec=0
AccuracySec=1min
Persistent=true'
SERVICE_TEXT='[Service]
ExecStart=
ExecStart=/usr/bin/env TRACKER_BACKUP_KEEP=48 /opt/tracker/.venv/bin/python -m scripts.tracker_backup create'

for existing in "$TIMER_DROP" "$SERVICE_DROP"; do
  if [[ -e "$existing" || -L "$existing" ]]; then
    [[ -f "$existing" && ! -L "$existing" ]] ||
      fail "Unexpected policy file type: $existing"
    [[ $(stat -c '%u' "$existing") == 0 ]] ||
      fail "Policy file must be root owned: $existing"
  fi
done

printf 'HOST=%s\n' "$(hostname -s)"
printf 'SCHEDULE=HOURLY RETENTION=48\n'
printf 'TIMER_SOURCE=%s\n' "$(systemctl show tracker-backup.timer -p FragmentPath --value)"
printf 'SERVICE_TRIGGER=%s\n' "$TRIGGERS"
if [[ "$MODE" == --audit ]]; then
  printf 'BACKUP_POLICY_AUDIT=PASSED (no changes)\n'
  exit 0
fi

install -d -o root -g root -m 0755 "$(dirname "$TIMER_DROP")" "$(dirname "$SERVICE_DROP")"
# Atomic writes, confined to the two policy-specific systemd drop-ins.
for target in "$TIMER_DROP" "$SERVICE_DROP"; do
  if [[ "$target" == "$TIMER_DROP" ]]; then content="$TIMER_TEXT"; else content="$SERVICE_TEXT"; fi
  temp="$(mktemp "$(dirname "$target")/.tracker-policy631.XXXXXXXX")"
  printf '%s\n' "$content" > "$temp"
  chmod 0644 "$temp"
  chown root:root "$temp"
  mv -f -- "$temp" "$target"
done
systemctl daemon-reload
systemctl restart tracker-backup.timer
systemctl is-active --quiet tracker-backup.timer ||
  fail "Backup timer failed after policy installation"
systemctl is-enabled --quiet tracker-backup.timer ||
  fail "Backup timer no longer enabled"
printf 'TIMER_CURRENT:\n'
systemctl list-timers --all tracker-backup.timer --no-pager
printf 'RETENTION_OVERRIDE:\n'
systemctl cat tracker-backup.service | tail -n 5
printf 'BACKUP_POLICY_APPLIED=HOURLY_KEEP_48\n'
