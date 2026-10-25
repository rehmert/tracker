#!/usr/bin/env sh
# Run on the VM from an account with sudo. Adjust the user, backup dir and service name if yours differ.
set -eu
cd /opt/tracker
sudo sh scripts/backup.sh "/mnt/backups"
sudo -u tracker git pull --ff-only
sudo -u tracker .venv/bin/pip install -q -r requirements.txt
sudo systemctl restart tracker
sleep 2
curl -fsS http://127.0.0.1:8000/healthz && echo " ok"
