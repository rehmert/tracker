#!/bin/bash
set -euo pipefail

SOURCE="/opt/tracker/backups"
DEST="/tracker-backups"
KEEP=90

# Verify the secondary directory exists.
if [[ ! -d "$DEST" ]]; then
    echo "ERROR: Secondary backup directory missing: $DEST" >&2
    exit 1
fi

# Copy backup archives without deleting destination files.
rsync -a \
    --include='tracker-*.zip' \
    --exclude='*' \
    "$SOURCE/" "$DEST/"

# Retain the newest 90 secondary backups.
mapfile -t archives < <(
    find "$DEST" -maxdepth 1 -type f -name 'tracker-*.zip' \
        -printf '%f\n' | sort -r
)

if (( ${#archives[@]} > KEEP )); then
    for archive in "${archives[@]:KEEP}"; do
        rm -- "$DEST/$archive"
    done
fi

echo "Replicated Tracker backups to $DEST"
