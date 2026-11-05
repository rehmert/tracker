#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" == 0 ]] || {
    echo 'Run as root' >&2
    exit 1
}

APP=/opt/tracker
PY="$APP/.venv/bin/python"

[[ -x "$PY" ]] || exit 1

umask 077
cd "$APP"

"$PY" - <<'PY'
from pathlib import Path
from app.pk_manifest269 import write_atomic

root=Path('/tmp/tracker-backups')
write_atomic(
    root,
    root/'release-manifest269.json'
)

print('Release manifest refreshed (root-only).')
print('Format: tracker-release-manifest-v1')
PY
