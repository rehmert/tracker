#!/usr/bin/env bash
set -euo pipefail

cd /opt/tracker

echo "========================================"
echo "Tracker Backup Recovery Audit"
echo "========================================"

.venv/bin/python -m app.backup_recovery "$@"
