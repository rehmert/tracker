# Release 768 — one-off guarded recovery of failed 767 PROD deploy

The user's read-only diagnostic demonstrated that the configured
`TRACKER_DATA_DIR` on PROD is relative and correctly resolves to
`/opt/tracker/data`. Tracker's service `WorkingDirectory` is
`/opt/tracker`, and the database exists. Release 767's strict
pre-install backup guard erroneously rejected *every relative path*,
before it could inspect integrity or create a snapshot.

Immutable failed deployment receipt:
`r767-deploy5d23aaf4` (status failed, exit 1,
`PromotionOrDeploymentGate`, `REMOTE_DEPLOY_EXIT_STATUS=1`).
GitHub main had already fast-forwarded to
`5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13`, but an independent read-only PROD check established the
installed commit remained Release 765:
`8c67580611fd945d9ae83f8015f071a24ab6fee5`;
Tracker service remained active.

## Fix (no 766 application changes)

- Resolve a relative configured data path against /opt/tracker, matching
  the running Tracker service. Retain checks for trusted env, real
  directory, actual SQLite database and rejection of database symlinks.
- Test relative, quoted, absolute and default paths with synthetic files,
  plus missing/symlink denial.
- Preserve Release 767's strict source review and complete verified
  private SQLite/upload snapshot **before** PROD source installation,
  exact device-table review, attachment hash checks and isolated restoration.
- Expand the existing signed PROD-side backup guard to include 768, and
  allow the exact failed-767-main / still-765-PROD catch-up in the DEV-side
  promoter. The new promotion is a *new signed target SHA*, not a replay.
- Add a **one-off controller transition** limited to the exact failed 767
  request and its immutable error receipt, allowing only a new Release 768
  qualification against installed DEV 767.
- A root-only **manual bootstrap** on tracker-dev must first verify that
  the immutable failure receipt, GitHub main, DEV source, and installed
  PROD source/service still match. It runs isolated regression tests and
  atomically replaces only the root-owned host release controller with
  this signed candidate, retaining a private previous copy.
  It does not install app data, deploy PROD, issue a release request, or
  modify any prior receipt. It cannot be repeated without reconciliation.
- After bootstrap the normal receipt-controlled exact-SHA lifecycle
  resumes: isolated qualification -> DEV install -> PROD preflight ->
  separate signed PROD deployment.
- All private DB backups remain on server with ten newest retained.
  Nothing private is uploaded to GitHub.

No changes under app/. Qualification scope includes controller history,
exact failure transition and negative cases, promoter recovery strict
ancestry/scope, data-path resolution, original 767 guard contracts, and
shared release-ops regressions. No PROD result can be marked successful
until its immutable final receipt verifies installed SHA and guarded
backup markers.

## Manual bootstrap

From tracker-dev, use the pinned exact GitHub branch SHA. Fetch the
branch and execute `scripts/tracker-recovery-bootstrap768.sh` from the
verified Git blob, as root. This is the only required manual bridge past
the failed 767 controller state; it does not bypass stage approval.
