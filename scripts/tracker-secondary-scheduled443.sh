#!/usr/bin/env bash
# Release 443: explicit opt-in systemd service runner, DEV only.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
ENV=/etc/tracker.env
PY="$APP/.venv/bin/python"

[[ "$(id -u)" -eq 0 ]] || {
    echo 'ERROR: Scheduled secondary backup requires root' >&2
    exit 1
}
[[ -f "$ENV" && ! -L "$ENV" && -x "$PY" ]] || {
    echo 'ERROR: Trusted Tracker environment or Python missing' >&2
    exit 1
}
[[ "$(stat -c %u "$ENV")" -eq 0 ]] || {
    echo 'ERROR: Tracker environment must be root-owned' >&2
    exit 1
}
# Root-controlled service configuration, same trusted environment as Tracker.
set -a
# shellcheck disable=SC1091
source "$ENV"
set +a
[[ "$TRACKER_INSTANCE" == DEV ]] || {
    echo 'ERROR: Refusing scheduled secondary backup on non-DEV host' >&2
    exit 1
}
exec "$PY" "$APP/scripts/tracker-secondary-ops443.py" run \
    --backup-dir /var/backups/tracker-secondary-dev \
    --keep 14
