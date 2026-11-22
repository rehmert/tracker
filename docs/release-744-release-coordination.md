# Release 744: source-only coordination guard for concurrent Work tasks

Verified DEV and PROD baseline: Release 743 commit
7585b65f003179fe86d0f98958fe0e63071b8e81.
Immutable prod receipt r743-deploy7585b65f passed. A separate Work task
then changed control/current.json to the earlier, already passed
r743-install7585b65f. That stale mutable pointer did not undo deployment.

The new scripts/tracker_release_coordination744.py validates each proposed
new command against current.json, latest.json, the immutable current
per-request receipt if the pointer is stale, exact installed DEV and main
commits, exact candidate branch HEAD, and explicit PROD authorization.

Safety rules:
- Never overwrite pending or unknown commands.
- A stale older command is recognized only after a verified fully passed
  PROD deployment of the exact same release and target. The historical
  743 safety hold can then be superseded by the first qualification of 744;
  completed PROD actions are never queued again.
- Stages advance qualify > dev_install > prod_preflight > prod_deploy
  with exact SHA, branch, request ID and preceding receipt.
- New SHA plus new request ID is mandatory after a failed qualification.
  Failed/unknown live actions are not retried. Only exact matching
  never-executed StageChainBlocked attempts may be retried.
- Production commands require separate explicit authorization.
- Every Work writer must re-fetch current, latest and branch SHA immediately
  before writing; invoke read-only validator on those snapshots; then use
  GitHub update_file content-SHA compare-and-swap. If the compare fails,
  stop and reconcile; never blindly retry or write a safety hold by
  rewinding an already-passed command.

This release adds offline source checks only. The installed root-owned
agent, remote GitHub branch permissions and event publisher do not change.
The helper cannot forcibly stop a concurrent task that ignores the protocol.
A future pinned host-agent installation or protected/append-only control
ref is necessary for server-enforced coordination. Do not claim that
server-side enforcement was added by this source-only release.

Only change-scoped isolated tests are requested, no full app suite.
No secrets, raw test logs, personal data, backups or package changes enter
GitHub. DEV install is guarded and PROD promotion remains separate.
The release-event PR #53 must stay open and unmerged.
