# Release 568 — DEV-controlled delivery and operations readiness

## Scope and safety

This release changes **tooling and documentation only**. No files under
`app/`, no SQL migrations, no dependency installations or upgrades, no
systemd edits and no CSRF policy changes. The existing
`scripts/tracker-release.sh` remains the guarded deployment engine on
both hosts. A scripts-only release does not require restarting Tracker.

Bundled improvements:

1. `scripts/tracker_promote568.py`: one stable DEV-side command for
   qualified-release checks, signing, transferring PROD approval, promoting
   GitHub main and invoking the existing guarded PROD deployment over
   **BatchMode SSH**.
2. `scripts/tracker_prod_remote568.sh`: a fail-closed executor streamed
   over DEV→PROD SSH, so PROD need not already contain this new helper.
   Rejects unexpected host/commit, verifies exact cryptographic approval,
   preserves the guarded backup/test/restore/runtime/rollback workflow, and
   recognizes already completed deployments only with success evidence.
3. `scripts/tracker_readiness568.py`: a read-only report of Python,
   SQLite, and installed direct dependency versions plus unpinned
   requirements. Optional `--security-audit` invokes the existing
   redacting security configuration audit.
4. Regression tests for the new argument, log-marker, security and
   invocation contracts.

## Workflow — one controlling host

### A. Qualify a new release on tracker-dev

Develop/test in a `release/<number>-<description>` branch. The installed
DEV `main` starts at an exact verified base SHA. Use the existing command:

```bash
sudo bash /opt/tracker/scripts/tracker-release.sh \
  --instance DEV --base <DEV_40_SHA> \
  --target <QUALIFIED_40_SHA> \
  --ref release/<number>-<description>
```

Retain its full successful output in
`/etc/tracker-release/release-<number>-dev.log` and append
`DEV_QUALIFIED_COMMIT=<QUALIFIED_40_SHA>` only after a successful
guarded deployment. Do not assert this marker before the runner succeeds.

Perform a real DEV browser review before authorizing a promotion.

### B. One DEV-side command for promotion + production deployment

The command has a **non-deploying dry-run by default**.

```bash
cd /opt/tracker
sudo /opt/tracker/.venv/bin/python scripts/tracker_promote568.py \
  --release <number> \
  --target <QUALIFIED_40_SHA> \
  --prod-base <PROD_INSTALLED_40_SHA> \
  --ref release/<number>-<description>
```

After reviewing the dry-run and UI, add `--execute` to that exact command.
It performs all remaining operations without logging into PROD.

Prerequisites: run as root on tracker-dev; clean installed main at target
SHA; existing root-only DEV qualification log; current DEV browser/strict-CSRF,
backend, restore and deployment evidence; signing private/public keys;
existing root→PROD key-based SSH with verified host key; expected PROD
base SHA and active Tracker; GitHub main at PROD base or already at target.

The release must not be promoted merely because backend tests passed:
the human DEV UI acceptance step is deliberately separate.

### Failure and retry behavior

- Failure before `--execute`: no signed approval, GitHub push or PROD deploy.
- Failure during signing/transfer: no GitHub push.
- Failure after successful GitHub promotion: the command prints
  `PROMOTED_BUT_PROD_NOT_VERIFIED=YES` and exits nonzero. Check the PROD
  status and rerun the same exact target/base rather than assuming success.
- On PROD, the executor delegates to the existing guarded runner.
  Backend-test or restore failure stops before installation; post-install
  failure uses the existing code-only rollback logic.
- If already installed, PROD must have a matching guarded success log
  and active service; otherwise the operation stops for investigation.
- No automatic cancellation or forced rollback of a GitHub promotion;
  remote deployment is separately authenticated and verified.

## Read-only dependency/security inventory

Run on each host **after** this tooling release is installed:

```bash
cd /opt/tracker
sudo .venv/bin/python scripts/tracker_readiness568.py --instance DEV
sudo .venv/bin/python scripts/tracker_readiness568.py \
  --instance DEV --security-audit
```

Use `--instance PROD` when running on PROD, or from DEV use the
existing SSH key to invoke the PROD commands directly.

The `--json` option produces a machine-readable dependency snapshot
(without security audit), useful for comparing installed versions between
hosts. It prints only package names and versions, not credentials or
environment-file contents.

**GitHub issue #10 remains open:** compare actual DEV/PROD dependency
resolutions, test exact pins in disposable builds, define update and
rollback policy and only then review a dependency change.

**GitHub issue #9 remains open:** the strict-CSRF browser gate already
tests a disposable candidate. The global service default is unchanged
until every relevant write route is assessed and the operator explicitly
approves rollout.

## Initial installation of Release 568

Because the new command is not present until Release 568 is installed,
use the **existing guarded DEV deployment** to install 568 and qualify
the change. After visual review, use the newly installed
`tracker_promote568.py` to promote and deploy Release 568 itself. The
remote executor is streamed from DEV, so no PROD-side helper bootstrap
is needed.

The operator does not need to open a shell on tracker-prod for normal
releases.
