#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" == 0 ]] || {
    echo 'Run as root' >&2
    exit 1
}

APP=/opt/tracker
PY="$APP/.venv/bin/python"

[[ -x "$PY" ]] || {
    echo 'Tracker virtualenv not available' >&2
    exit 1
}

case "${1:-}" in
    ''|--json) ;;
    *)
        echo 'Usage: tracker-release-health237.sh [--json]' >&2
        exit 2
        ;;
esac

cd "$APP"

"$PY" - "${1:-}" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

from app.pk_release_report253 import collect

result=collect(Path('/tmp/tracker-backups'))

result['running_commit']=subprocess.check_output(
    ['git','rev-parse','--verify','HEAD'],
    text=True
).strip()

result['service_active']=(
    subprocess.run(
        ['systemctl','is-active','--quiet','tracker'],
        check=False
    ).returncode==0
)

if sys.argv[1]=='--json':
    print(json.dumps(result,indent=2))
else:
    print('Commit:',result['running_commit'])
    print('Tracker service active:',result['service_active'])

    for item in result['entries']:
        print(
            item['started'] or 'unknown',
            item['instance'] or 'unknown',
            item['status']
        )
PY
