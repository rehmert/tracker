# Release 523 — DEV is the test platform, PROD runs the same features

Base: Release 522 `4f62861182bd14cc5a13a3306dc6c83211e4ebe6`.

## Goal

A qualified change is tested on DEV and then promoted to PROD. The instance
label identifies which data/service is in use; it must **not** permanently
disable features on PROD.

Release 523 removes the previous permanent DEV-only restrictions on:

- Administrator browser login, signed session cookies, session expiry,
  "remember me", logout, session revocation, account-password changes;
- The shared unified login for administrators and separately provisioned
  secondary users, with private workspace navigation;
- Administrator-only secondary-user account creation/credential editing;
- The **existing, currently DEV-qualified** isolated secondary private
  workspace workflows (Vitals, inventory, dose, reconstitution, corrections,
  food/water, supplies, usage and attachments), each with its existing feature
  gate, idempotency and worker isolation;
- Secondary account backup/recovery tooling, with separate PROD archive paths.

This is **functional parity with the current DEV feature set**. It is **not**
a claim that every administrator route is available to a secondary account.
In both environments, the normal Tracker dashboard/primary database remains
administrator-only, and other users use the private `/secondary` workspace.
The existing source-level full-main-app cutover audit deliberately remains
blocked until that larger feature parity is separately implemented.

## Independent instances

- DEV: unchanged `TRACKER_INSTANCE=DEV`, existing marker
  `.tracker-session-auth-dev`, separate existing DEV auth/data.
- PROD: `TRACKER_INSTANCE=PROD`, distinct new marker
  `.tracker-session-auth-prod523` **and** explicit
  `TRACKER_PROD_PARITY523=1` required. Without both, PROD retains its
  current Basic Auth behavior.
- The PROD session authentication database is initialized from the **current
  PROD Basic Auth credentials**, using a separate SQLite file inside PROD's
  own data root. The script never prints, uploads or places passwords on the
  command line. DEV users, credentials and data are never copied to PROD.
- An existing incompatible PROD auth database causes a failed cutover rather
  than password replacement.
- Separate PROD feature flags mirror the qualified DEV multi-user flag list.
  Existing secondary-user credentials/data must be provisioned independently
  in PROD by the administrator through Account Security > Manage Users.

## Deployment and cutover

1. Run the normal pinned guarded release on **DEV**. All existing regression,
   standard+strict browser, backup/restore tests must pass. A **third**
   disposable Chromium gate starts the candidate as **PROD**, with temporary
   credentials and a separate auth marker, and verifies administrator login,
   account security/users, private secondary login, admin denial and logout.
2. Promote **only** the exact DEV-qualified SHA to GitHub main.
3. Deploy that exact SHA to PROD using the existing guarded release runner.
   Until activation, PROD continues to use Basic Auth and keeps all data.
4. On PROD, run
   `sudo /opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker-prod-parity523.py enable`.
   This independently verifies the PROD identity, live service, clean main
   checkout, existing credentials, database, and absence of pre-existing
   cutover artifacts. It creates the separate auth DB with existing PROD
   credentials, applies a root-owned config drop-in and distinct marker,
   restarts the service, verifies the effective flags, anonymous browser
   redirect to /login, authenticated 35+ sidebar-page smoke via a *revocable*
   session, and a verified private account backup. On any failure, it removes
   the opt-in artifacts and restarts the former Basic-auth path.
5. Verify externally through the actual LAN HTTPS reverse proxy that PROD
   offers the login page, sign-in/sign-out, account security, a private
   secondary account, and a successful Vitals write. External reverse-proxy
   HTTP Basic Authentication, if configured independently of Tracker, cannot
   be disabled by changes to the FastAPI application.
6. Privileged local recovery works for both instance types with
   `scripts/tracker-auth-recover386.py`. No root HTTP bypass is introduced.

## Private data backups

The original Tracker archive contains primary `tracker.db` and its uploads,
not the separate authentication database or secondary users. Following
activation, every **future PROD release** also runs a verified root-private
auth/secondary snapshot **before** code installation. A cutover baseline
snapshot is required before activation is reported successful.

`scripts/tracker-prod-parity523.py backup` provides a manually runnable
verified snapshot between releases. Private PROD archives are in
`/var/backups/tracker-secondary-prod` (root-owned mode 0700); files are
mode 0600 and contain credentials and potentially private health data.
Use appropriate off-host encryption and a retention/backup policy separately;
a release backup is not a substitute for scheduled protection.

## Rollout safety

- Updating code alone does not change PROD authentication.
- No production database schema migrations or arbitrary password resets.
- No DEV private SQLite files, credential hashes or sessions enter PROD.
- Existing authentication, user isolation and CSRF/origin guards remain.
- Login requires HTTPS in the user's browser because auth cookies are Secure.
- GitHub is only source control; tests run inside the guarded DEV LXC
  qualification system (no Actions or hosted CI).
