#!/usr/bin/env sh
# Release 420: retired unsafe update entry point. No side effects.
set -eu
printf '%s\n' \
  'BLOCKED: scripts/update.sh has been retired.' \
  'Use the guarded scripts/tracker-release.sh workflow with pinned commits.' \
  'This command has not changed code, dependencies, services, or data.' >&2
exit 2
