# DEV-controlled staged production promotion for Workout 654–657

**Use on tracker-dev only. Do not run commands on tracker-prod manually.**

The ordinary Release 568 promotion command validates that the currently
installed DEV commit is the exact promoted target. DEV is already on 657;
PROD is still on 653. Therefore historical 654/655 schema changes cannot
be promoted through the ordinary single-commit preflight unchanged.

This operations-only companion uses the **installed trusted Release 568
functions** for Ed25519 signing, public-key verification, transfer of signed
approval to PROD, GitHub fast-forward and BatchMode SSH. The remote
executor is based on the established tracker_prod_remote568.sh and executes
the exact target release runner, not the older installed PROD runner.

Stage chain is hardcoded and immutable:

- 654: 653 -> 654, reviewed workout-654 schema flag + verified backup
- 655: 654 -> 655, reviewed workout-655 schema flag + verified backup
- 656: 655 -> 656, source-only
- 657: 656 -> 657, source-only

For **every** step, DEV must be clean main at exact qualified 657, the
historical release's root-only qualification log must satisfy the existing
verified_log validator for the exact target, and the original release
branch must still point to that SHA. GitHub main must be either the prior
stage or the target, with ordinary fast-forward promotion only. PROD must
be on the expected prior stage, or already at that same stage with
verified success evidence. DEV's trusted SSH host key, cryptographic
signing keys, and the existing PROD signed-approval validator are required.

The remote runner enforces root on tracker-prod, immutable stage pair,
strict PROD attachment integrity, pre-migration SQLite/upload backup with
isolated restore, isolated qualification, service health and rollback
conditions. No PROD data is synchronized from DEV.

Use the two immutable, blob-verified GitHub scripts from tracker-dev.
Run --all --execute to process the four stages **in sequence**, stopping
immediately on any failed verification or deployment. A dry run checks
only the current first stage because later stages require prior ones
to have been installed. For recovery, --release 654|655|656|657 --execute
handles one stage; it will not skip a stage or forge qualification.
There is no need to update the live DEV app.

The source branch is ops/workout-prod-staged657, descended from the
DEV-qualified Release 657 commit. These tooling files are streamed and
removed by the operator's wrapper; they are not installed on either host.

Physical mobile-camera QA was not performed; Chromium Android/iPhone
emulation QA did pass. The camera is a progressive enhancement with a
manual QR fallback.
