#!/usr/bin/env bash
set -euo pipefail

cd /opt/tracker

[[ $(id -u) -eq 0 ]] || {
    echo "ERROR: Run as root"
    exit 1
}

[[ $(systemctl show -p User --value tracker.service) == tracker ]] || {
    echo "ERROR: Unexpected service user"
    exit 1
}

[[ $(systemctl show -p Group --value tracker.service) == tracker ]] || {
    echo "ERROR: Unexpected service group"
    exit 1
}

systemctl is-active --quiet tracker.service

/opt/tracker/.venv/bin/python - <<'PY'
import getpass
import json
import os
import subprocess
from pathlib import Path

pid = subprocess.check_output(
    [
        "systemctl", "show", "-p", "MainPID",
        "--value", "tracker.service"
    ],
    text=True,
).strip()

if not pid.isdecimal() or int(pid) <= 1:
    raise SystemExit("ERROR: Tracker service inactive")

live = {}
for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
    if b"=" in item:
        k, v = item.split(b"=", 1)
        live[k.decode()] = v.decode()

if live.get("TRACKER_INSTANCE") != "DEV":
    raise SystemExit("ERROR: Not a DEV instance")

data_root = live.get("TRACKER_DATA_DIR", "./data")
configured = (Path("/opt/tracker") / data_root).resolve()

if configured != Path("/opt/tracker/data"):
    raise SystemExit("ERROR: Unexpected data directory")

with open("/dev/tty", "r") as tty:
    print("New secondary username: ", end="", flush=True)
    username = tty.readline().strip()

password = getpass.getpass("Password: ")
confirm = getpass.getpass("Confirm password: ")

payload = json.dumps({
    "username": username,
    "password": password,
    "confirmation": confirm,
})

command = [
    "runuser", "-u", "tracker", "--",
    "env",
    "TRACKER_INSTANCE=DEV",
    "TRACKER_DATA_DIR=/opt/tracker/data",
    "/opt/tracker/.venv/bin/python",
    "-m", "app.secondary_provision479",
]

result = subprocess.run(
    command,
    input=payload,
    text=True,
    cwd="/opt/tracker",
    check=False,
)

del password, confirm, payload

if result.returncode:
    raise SystemExit(
        "ERROR: Secondary provisioning failed"
    )

print("PASS: Provisioned as tracker service identity")
PY
