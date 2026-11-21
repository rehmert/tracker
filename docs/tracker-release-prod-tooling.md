# Tracker PROD promotion helper

Stable branch: tracker-release-tooling. Script: scripts/tracker-release-prod.sh.

Purpose: fetch and run a current, reusable DEV-controlled signed PROD release wrapper.
Never merge this tooling-only branch into main. It is separate from installed
application releases and cannot substitute for production authorization.

Run on tracker-dev (replace 726 to assert a different expected DEV release):

```bash
sudo bash -c '
  set -euo pipefail
  cd /opt/tracker
  git -c safe.directory=/opt/tracker fetch --no-tags origin \
    refs/heads/tracker-release-tooling:refs/remotes/origin/tracker-release-tooling
  SCRIPT=$(git -c safe.directory=/opt/tracker show \
    refs/remotes/origin/tracker-release-tooling:scripts/tracker-release-prod.sh)
  bash -n <<<"$SCRIPT"
  bash -s -- 726 <<<"$SCRIPT"
'
```

Every run fetches the newest tooling version and checks its Bash syntax before execution, without modifying the installed checkout.
The optional expected release argument prevents promotion of an unintended version.
Alternatively omit the argument to select the release currently installed on DEV.

The wrapper verifies installed DEV release/ref and exact SHA; interrogates PROD via
authenticated SSH to detect installed commit and release; compares origin/main;
runs host-side tracker_promote568.py preflight then --execute if allowed; tails
a root-only operation log until completion; independently verifies PROD service,
PROD HEAD, and origin/main. A failure halts without automatic retries.

Running the wrapper is an explicit PROD approval. No credentials, personal data,
medical information, raw logs, or backups are committed to GitHub.
