#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run as root' >&2; exit 1; }
APP=/opt/tracker
[[ -d "$APP/.git" ]] || { echo 'Tracker checkout missing' >&2; exit 1; }
echo "Running commit: $(git -C "$APP" rev-parse --verify HEAD)"
echo "Service: $(systemctl is-active tracker || true)"
echo 'Recent guarded release results (no log content or paths):'
find /tmp/tracker-backups -maxdepth 2 -type f -name deployment.log -path '*/release.*/deployment.log' -printf '%T@ %p\n' 2>/dev/null |
  sort -nr | sed -n '1,8p' | cut -d' ' -f2- | while IFS= read -r log; do
    result="$(sed -n 's/^EXIT_STATUS=//p' "$log" | tail -n 1)"
    case "$result" in 0) result=SUCCESS;; [1-9]*) result=FAILED;; *) result=UNKNOWN;; esac
    stamp="$(grep -m1 '^Started:' "$log" | cut -d';' -f1 | cut -d' ' -f2- || true)"
    printf '%s  %s\n' "${stamp:-unknown}" "$result"
  done
