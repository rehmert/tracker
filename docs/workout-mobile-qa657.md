# Release 657 — DEV-only mobile functional browser qualification

This is an operator-run QA utility, NOT a release, migration, or deployment.
It does not modify installed source, the live DEV database, or PROD.

## Baseline

Installed DEV must be exactly b9487d4b1fab176255b398833c51c9a2da79f042,
the successfully DEV-qualified Release 657 commit.

The QA code lives on the qa/657-mobile-functional source branch,
descended directly from 657. Only these files may differ from the approved
baseline:

- scripts/tracker-workout-mobile-qa657.sh
- tests/browser/test_workouts_mobile657.py
- docs/workout-mobile-qa657.md

## Automated real Chromium QA

The runner verifies the DEV hostname, instance identity, clean installed
baseline and pinned GitHub commit before making a detached QA worktree in
/tmp. It creates a new disposable SQLite database and serves the reviewed
candidate on loopback-only uvicorn behind the existing local test HTTPS
proxy. It never loads /etc/tracker.env into the candidate.

With strict CSRF enforcement enabled, Playwright Chromium emulates an
Android viewport (393x852) and an iPhone viewport (390x844), including touch.
Each emulated phone exercises actual browser form submissions:

1. Add two gym machines and verify they render.
2. Look up a known machine using its QR code text.
3. Save a routine, add both machines in order, and start.
4. Record a set, repeat last set, and check the count.
5. Correct the newest set, validate edit confirmation and redirect.
6. Confirm and remove the corrected set.
7. Follow the Next machine link, log a set, and finish.
8. Review the historical session and recorded per-machine progress.
9. Scan an unknown QR value through the internal browser lookup path and
   verify the Add Equipment form is prefilled.

The test blocks off-host browser requests. No real phone camera hardware or
live phone permissions are accessed; a physical device check remains useful
before PROD. It does not claim production readiness by itself.

When the runner exits it stops its temporary server and proxy, detaches
the worktree, deletes the disposable test SQLite database and test TLS key,
and prints a success/failure marker. The operator retains the command output
as evidence; never use GitHub Actions, PRs, or cloud services as QA runners.

No schema updates, backup changes, installed app restarts, PROD changes or
full unrelated regression suite are required.
