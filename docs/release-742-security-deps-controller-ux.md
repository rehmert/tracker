# Release 742 — One combined security, dependency, release-chain and UX release

Exact baseline: Release 741 installed on DEV, PROD and GitHub main
`c5efed6b40f4324187eff3e83dbed44d9e68f5c4`.
Candidate ref: `release/742-security-deps-controller-ux`.
This is **one source-only release**. No requirements/venv/schema/data migration,
live credential access, restart beyond the standard guarded source deployment,
strict-CSRF activation, release-agent substitution, PROD deployment,
network calls or GitHub-uploaded raw evidence.

## Security / CSRF (outstanding issue #9)

Release 742 adds `scripts/tracker_security_readiness742.py`, a deterministic
read-only scan using the existing registered unsafe route-declaration scanner.
The frozen historical Release 627/705 CSRF counts are not treated as proof
for newer endpoints. Recent Supply, Supply Category, Workout Equipment,
Workout Routine and Saved Food MACD writes are explicitly reported as
**not yet proven** with signed-positive, unsigned-negative, HTTP, HTTPS and
multipart/runtime evidence. The command checks the report-only source default.

Run on a checked-out source tree:
```bash
/opt/tracker/.venv/bin/python scripts/tracker_security_readiness742.py --json
```
`--require-strict-ready` returns nonzero until completed independent
runtime testing and manual review are available. This is intentional, not
permission to bypass the gate. Existing Origin/Fetch Metadata, session auth,
specific signed actions and CSRF reporting remain unchanged.
`TRACKER_CSRF_ENFORCE=1` is **NOT** enabled by this release. All new
security code is an offline inventory and acceptance guard, not a new
production CSRF enforcement mechanism.

Issue #9 remains open until the full strict native/HTMX/multipart HTTP/HTTPS
browser evidence is established for all unsafe routes, route-specific review
is complete, and an explicit DEV opt-in with rollback is qualified.

## Dependency and Chromium / OS provenance (issue #10)

Release 569 already has a 44-package DEV/PROD observed Python 3.13.5
inventory, and Release 705 added the privately sourced SHA-hashed wheelhouse
and independent offline two-pass Python replay. Do NOT create a conflicting
requirements lock or change installed dependency versions.

`scripts/tracker_browser_provenance742.py` adds a read-only browser/OS
fingerprint and DEV/PROD comparison for the missing *non-Python* evidence:
Chromium executable SHA-256 and byte length, Python, installed Playwright
distribution version, OS ID/version and libc. Results do not contain host
paths, user data or credentials. The executable is **never run**, installed
or downloaded by this script. The capture receipt goes only into an
explicit private (0700) directory under /tmp and is created 0600 and
no-clobber.

Example operator-side steps, with a browser executable selected from the
already installed local Playwright installation:
```bash
mkdir -m 700 /tmp/tracker742-browser-local
/opt/tracker/.venv/bin/python scripts/tracker_browser_provenance742.py \
  --capture /path/to/installed/chromium-executable \
  --output /tmp/tracker742-browser-local/dev.json
# Copy a separately captured sanitized PROD receipt into the same
# private directory without copying any binary or credentials to GitHub.
# Then compare on DEV:
/opt/tracker/.venv/bin/python scripts/tracker_browser_provenance742.py \
  --compare /tmp/tracker742-browser-local/dev.json \
            /tmp/tracker742-browser-local/prod.json
```

Matching fingerprints do **not** prove independently approved binary
provenance, OS shared-library reproducibility, full HTTP/HTTPS browser QA
or tested dependency+Chromium rollback. `--require-complete` deliberately
refuses to declare those gates complete without external reviewed evidence.
Issue #10 stays open until independently tested OS/Chromium rollback and
full offline reproducibility; no dependency update is performed.

## Stage chain / PROD lag (issue #11)

`scripts/tracker_stage_chain742.py` implements an independent, read-only
receipt contract for the cumulative DEV-ahead-of-PROD scenario:

- Qualification and DEV-install bases must match one another; the full
  target, release ref, release number, immutable request ID, prior successful
  stage, result markers and completion times must be verified.
- PROD preflight and deployment bases must match the **actually installed
  PROD commit**, which may legitimately differ from the preceding
  qualification/DEV-install base. Both are separately checked to be ancestors
  of the **exact target** with `git merge-base --is-ancestor`.
- Duplicate request IDs, stage gaps, stale targets, invalid timestamps,
  incorrect prior-stage IDs, missing successful deployment markers, GitHub
  main drift and non-ancestor bases fail closed.
- No overwrite of host-side controller or bypass of signed approvals,
  PROD authentication, rollback or active-service checks.

Use copies of sanitized immutable receipts, not the notification PR:
```bash
/opt/tracker/.venv/bin/python scripts/tracker_stage_chain742.py \
  --release 742 --ref release/742-security-deps-controller-ux \
  --target EXACT_TARGET_SHA --prod-base INSTALLED_PROD_SHA \
  --main-sha CURRENT_MAIN_SHA \
  --qualify /private/receipts/qualification.json \
  --dev-install /private/receipts/dev-install.json \
  --prod-preflight /private/receipts/prod-preflight.json
```
This is an executable specification and synthetic negative regression
coverage; **the host-side release-event agent is outside this GitHub
source tree and has not been modified**. Issue #11 cannot be closed until
its implementation and a real catch-up preflight are reviewed and pass.

## Global UI/CSS request consolidation (remaining issue #54)

- The base template's adjacent, global Release 679 component and Release
  676 shortcut layers now load from the **same existing**
  `tracker-ui-foundation679.css?v=742` file, saving one global stylesheet
  request without changing the cascade or creating another CSS file.
- The original shortcut rules are appended verbatim to the end of the
  679 layer; original legacy 676 stylesheet is kept as a standalone
  fixture/reference for older direct-load tests.
- All original selector specificity, media rules, dark/light tokens,
  44px tap targets and downstream Rapid Gym `tracker-workout-nav-density681`
  order are preserved.
- Add Chromium computed-style parity on 320, 390, 430, 760 and 1024px
  in light/dark preferences, plus the legacy 676/679/680/681 tests.

The current application still has many historical CSS files; this release
consolidates one proven safe global request pair, not the whole application
stylesheet library. Do not remove files used by historical tests or
other templates without reference- and browser-parity review.

## One coherent qualification and DEV installation

- Pinned Release 741 clean DEV baseline, exact candidate SHA, private
  systemd network namespace, diff allowlist, immutable receipts.
- Syntax/import, static route and CSRF default, provenance and stage-chain
  forged receipt cases, source asset integrity, Chromium computed parity,
  and focused existing CSS/security/dependency/controller regressions.
- Guarded DEV installation only after qualification passes; no PROD
  preflight or deployment without a separate explicit instruction.
- Full browser/full backend tests may be run for shared-security changes;
  the source-only readiness checker does not assert full runtime clearance.

## Completion boundary

This release improves the *readiness infrastructure and one shared UX CSS
path* in a single source release. It does not pretend the outstanding strict
CSRF opt-in, third-party supply-chain approval, host-controller integration
or complete CSS retirement are finished. Their independent evidence remains
operator-gated and cannot be safely satisfied by just committing source code.
