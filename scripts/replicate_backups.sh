#!/usr/bin/env bash
# Verified, fail-closed secondary-local backup replication. No remote transfers.
set -Eeuo pipefail
umask 077
cd /opt/tracker
exec /opt/tracker/.venv/bin/python \
    /opt/tracker/scripts/tracker_replica.py "$@"
