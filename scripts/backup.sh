#!/usr/bin/env sh
# Release 421: retired legacy backup entry point. No filesystem writes.
set -eu
printf '%s\n' \
  'BLOCKED: scripts/backup.sh has been retired.' \
  'The old two-part SQLite/uploads backup is unsupported.' \
  'Use the verified administrator backup command from /opt/tracker:' \
  '/opt/tracker/.venv/bin/python -m scripts.tracker_backup create' >&2
exit 2
