#!/usr/bin/env bash
set -euo pipefail

APP=/opt/tracker
UNIT=tracker.service
DROPIN_DIR=/etc/systemd/system/tracker.service.d
DROPIN="$DROPIN_DIR/90-tracker-multiuser475.conf"
MARKER="Tracker multi-user DEV launch Release 475"

FLAGS=(
    TRACKER_SECONDARY_PREVIEW430
    TRACKER_MULTIUSER_LOGIN473
    TRACKER_SECONDARY_VITAL_WRITES433
    TRACKER_SECONDARY_DOSE_WRITES434
    TRACKER_SECONDARY_INVENTORY_WRITES435
    TRACKER_SECONDARY_FOOD_WRITES456
    TRACKER_SECONDARY_SUPPLY_WRITES438
    TRACKER_SECONDARY_SUPPLY_USE439
    TRACKER_SECONDARY_RECONSTITUTION_WRITES436
    TRACKER_SECONDARY_VIAL_CORRECTIONS437
    TRACKER_SECONDARY_ATTACHMENT_UPLOAD472
)

die() {
    echo "ERROR: $*" >&2
    exit 1
}

require_dev() {
    [[ $(id -u) -eq 0 ]] || die "Root required"
    [[ -f "$APP/.env" ]] || die "DEV .env missing"

    grep -Eq \
      '^TRACKER_INSTANCE=["\047]?DEV["\047]?$' \
      "$APP/.env" || die "DEV instance required"

    [[ -x "$APP/.venv/bin/python" ]] ||
        die "Application virtualenv missing"

    systemctl cat "$UNIT" >/dev/null ||
        die "Tracker systemd unit missing"
}

check_process_flags() {
    local desired="$1"

    local pid
    pid=$(systemctl show \
        --property MainPID --value "$UNIT")

    [[ "$pid" =~ ^[0-9]+$ ]] ||
        die "Invalid service PID"

    [[ "$pid" -gt 1 ]] ||
        die "Tracker is not running"

    [[ -r "/proc/$pid/environ" ]] ||
        die "Cannot inspect live service environment"

    "$APP/.venv/bin/python" \
        - "/proc/$pid/environ" "$desired" \
        "${FLAGS[@]}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
desired = sys.argv[2]
names = sys.argv[3:]

env = {}
for entry in path.read_bytes().split(b"\0"):
    if b"=" in entry:
        key, value = entry.split(b"=", 1)
        env[key.decode(errors="replace")] = (
            value.decode(errors="replace")
        )

if env.get("TRACKER_INSTANCE") != "DEV":
    raise SystemExit("ERROR: Running process is not DEV")

if desired == "1":
    bad = [
        name for name in names
        if env.get(name) != "1"
    ]
else:
    # Lockdown also disables the secondary preview.
    bad = [
        name for name in names
        if env.get(name, "0") == "1"
    ]

if bad:
    raise SystemExit(
        "ERROR: Effective environment mismatch: "
        + ", ".join(bad)
    )

print("PASS: Live process flags verified")
print("MODE=" + (
    "MULTIUSER_DEV_ENABLED"
    if desired == "1"
    else "MULTIUSER_DEV_DISABLED"
))
PY
}

status() {
    require_dev

    echo "=== TRACKER MULTI-USER STATUS ==="
    echo "Unit: $UNIT"

    systemctl is-active "$UNIT"

    if [[ -f "$DROPIN" ]]; then
        grep -Fq "$MARKER" "$DROPIN" ||
            die "Unrecognized launch drop-in"
        echo "Launch configuration: installed"
    else
        echo "Launch configuration: absent"
    fi

    local pid
    pid=$(systemctl show \
        --property MainPID --value "$UNIT")

    if [[ ! "$pid" =~ ^[0-9]+$ ]] ||
       [[ "$pid" -le 1 ]]; then
        die "Tracker has no active main process"
    fi

    "$APP/.venv/bin/python" \
        - "/proc/$pid/environ" \
        "${FLAGS[@]}" <<'PY'
import sys
from pathlib import Path

env = {}
for entry in Path(sys.argv[1]).read_bytes().split(b"\0"):
    if b"=" in entry:
        key, value = entry.split(b"=", 1)
        env[key.decode(errors="replace")] = (
            value.decode(errors="replace")
        )

print("TRACKER_INSTANCE=" + env.get(
    "TRACKER_INSTANCE", "UNSET"
))

for name in sys.argv[2:]:
    print(name + "=" + env.get(name, "UNSET"))

print(
    "LOCKDOWN=" +
    env.get("TRACKER_SECONDARY_LOCKDOWN440", "UNSET")
)
PY
}

enable() {
    require_dev

    [[ ! -e "$DROPIN" ]] ||
        die "Launch drop-in already exists; no overwrite"

    [[ ! -L "$DROPIN_DIR" ]] ||
        die "Symlinked drop-in directory rejected"

    systemctl is-active --quiet "$UNIT" ||
        die "Tracker service must be healthy"

    [[ -z $(git -C "$APP" status --porcelain) ]] ||
        die "DEV working tree is dirty"

    # The auditor must prove that expected guards remain.
    # It does NOT claim full primary-app parity.
    cd "$APP"

    TRACKER_INSTANCE=DEV \
    "$APP/.venv/bin/python" - <<'PY'
from app.multiuser_audit474 import audit474

report = audit474()

assert all(report["checks"].values())
assert report["full_main_app_cutover_ready"] is False

print("PASS: Verified DEV pilot security boundaries")
print("NOTICE: Full primary-app cutover remains blocked")
PY

    mkdir -p "$DROPIN_DIR"

    local temp
    temp=$(mktemp "$DROPIN_DIR/.multiuser475.XXXXXXXX")

    {
        echo "# $MARKER"
        echo "[Service]"
        echo "Environment=TRACKER_SECONDARY_LOCKDOWN440=0"
        for name in "${FLAGS[@]}"; do
            echo "Environment=${name}=1"
        done
    } > "$temp"

    chmod 0644 "$temp"
    mv "$temp" "$DROPIN"

    # Any failure restores the previous disabled state.
    rollback_enable() {
        echo "ROLLBACK: Disabling Release 475 flags"
        rm -f "$DROPIN"
        systemctl daemon-reload
        systemctl restart "$UNIT" || true
    }

    trap rollback_enable ERR

    systemctl daemon-reload
    systemctl restart "$UNIT"
    systemctl is-active --quiet "$UNIT"

    check_process_flags 1

    trap - ERR

    echo "=== MULTI-USER DEV PILOT ENABLED ==="
    echo "Shared login: /login"
    echo "Private workspace: /secondary/overview"
    echo "Original administrator routes remain protected"
}

disable() {
    require_dev

    if [[ -f "$DROPIN" ]]; then
        grep -Fq "$MARKER" "$DROPIN" ||
            die "Refusing to remove unrecognized drop-in"
        rm "$DROPIN"
    fi

    systemctl daemon-reload
    systemctl restart "$UNIT"
    systemctl is-active --quiet "$UNIT"

    # Existing environment files can override systemd
    # Environment values. Refuse to report disabled
    # if the effective service still has any launch flag.
    check_process_flags 0

    echo "=== MULTI-USER DEV PILOT DISABLED ==="
}

case "${1:-}" in
    enable) enable ;;
    disable) disable ;;
    status) status ;;
    *)
        echo "Usage: $0 enable|disable|status" >&2
        exit 2
        ;;
esac
