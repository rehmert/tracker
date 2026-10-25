#!/usr/bin/env sh
# Consistent backup of the SQLite DB plus uploaded COAs.  Usage: scripts/backup.sh /path/to/backups
set -eu
DATA="${TRACKER_DATA_DIR:-$(dirname "$0")/../data}"
OUT="${1:?usage: backup.sh <dest-dir>}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
sqlite3 "$DATA/tracker.db" ".backup '$OUT/tracker-$STAMP.db'"
tar -czf "$OUT/uploads-$STAMP.tar.gz" -C "$DATA" uploads
echo "Backed up to $OUT (stamp $STAMP)"
