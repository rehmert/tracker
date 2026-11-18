#!/usr/bin/env bash
# Release 687 incident investigation: READ ONLY. No tests or deployments.
set -u
printf 'TRACKER_SSH_DIAGNOSTIC_BEGIN=%s\n' "$(date -u +%FT%TZ)"
printf 'HOST=%s\n' "$(hostname -s)"
printf 'WHOAMI=%s\n' "$(id -un)"
printf '\n=== SERVICE STATE ===\n'
systemctl is-active tracker ssh sshd 2>/dev/null || :
printf '\n=== MEMORY AND CGROUP ===\n'
free -h || :
for p in /sys/fs/cgroup/memory.events /sys/fs/cgroup/system.slice/memory.events /sys/fs/cgroup/system.slice/ssh.service/memory.events /sys/fs/cgroup/system.slice/sshd.service/memory.events; do
  if test -r "$p"; then printf '%s\n' "$p"; cat "$p"; fi
done
printf '\n=== KERNEL MEMORY / PROCESS TERMINATIONS (LAST 6 HOURS) ===\n'
journalctl --no-pager --since '6 hours ago' -k -o short-iso 2>/dev/null |
  grep -Ei 'oom|out of memory|killed process|memory cgroup|systemd-oomd|segfault|process .*killed|task .*blocked' | tail -n 100 || :
printf '\n=== SYSTEMD OOM DAEMON (LAST 6 HOURS) ===\n'
journalctl --no-pager --since '6 hours ago' -u systemd-oomd -o short-iso 2>/dev/null | tail -n 70 || :
printf '\n=== SSH SERVICE EVENTS (LAST 6 HOURS, FILTERED) ===\n'
journalctl --no-pager --since '6 hours ago' -u ssh -u sshd -o short-iso 2>/dev/null |
  grep -Ei 'disconnect|session closed|killed|terminated|failed|error|restarted|stopping|starting|connection closed' |
  sed -E 's/from ([0-9]{1,3}\.){3}[0-9]{1,3}/from [IP REDACTED]/g;s/rhost=([0-9]{1,3}\.){3}[0-9]{1,3}/rhost=[IP REDACTED]/g' |
  tail -n 110 || :
printf '\n=== RELEVANT DEPLOYMENT / TEST SERVICE EVENTS ===\n'
journalctl --no-pager --since '6 hours ago' -o short-iso 2>/dev/null |
  grep -Ei 'tracker.*(oom|killed|memory|max|failed)|pytest.*(oom|killed)|chromium.*(oom|killed)' |
  tail -n 80 || :
printf '\n=== SHELL LIMITS ===\n'
ulimit -a || :
printf 'TRACKER_SSH_DIAGNOSTIC_END=%s\n' "$(date -u +%FT%TZ)"
