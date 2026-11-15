# Release 628 — PK Simulator simplified entry and graph

## Scope

DEV-first, presentation-only UX refinement atop qualified Release 627
`07d807a061f6a1b2ef4f25007967d70b10383f51`.

- Replace numbered mode titles with action-oriented "Use a protocol",
  "Build a schedule", "Compare scenarios" and "Compare schedules".
  Preserve all four existing `data-pk-mode` values and their saved mode
  selection.
- Add a three-step quick start at the top, emphasizing that simulated
  graphs do not record administrations or change inventory.
- Make recorded-only, recorded-plus-planned, and today's dashed graph
  reference immediately understandable above the chart.
- Put graph layer toggles, zoom/pan and analysis JSON export behind an
  accessible, initially closed "Graph options and exports" disclosure.
  Keep the time-window presets, canvas, metrics and existing graph exports
  accessible. Preserve all original control IDs for existing scripts.
- Collapse verbose multi-schedule explanatory paragraphs behind a
  "Schedule tips, alignment and import details" disclosure while keeping
  schedule editors and actions immediately available.
- Improve narrow-screen workflow tabs, quick-start layout, graph framing,
  time-window buttons and metrics.
- Add a small read-only graph message announcing the plotted time span
  after an existing `tracker:pk-graph-updated` event. No API calls,
  persistence, storage, or pharmacokinetic algorithm changes.

## Verification and deployment contract

`tests/test_release628_pk_simplified.py` validates Jinja parsing,
unique existing element IDs, graph and schedule disclosure placement,
asset references, read-only JS and browser-test registration.
The pre-existing qualified
`tests/browser/test_pk_smoke_281.py` was extended instead of creating
a new browser module, so Release 511's strict/standard test inventory
is unchanged. It checks workflow actions, collapsed graph options,
a narrow viewport and a synthetic graph update without any write.
The Release 628 source test is included in the early focused
regression gate.

The guarded DEV release runner still performs original mandatory
Chromium HTTP/HTTPS, complete backend regressions, backup,
installation, health check and automatic code rollback on post-install
failure. Do not enable global strict CSRF or deploy PROD as part of
this release.

## Known boundaries

This release simplifies navigation and presentation without replacing
the underlying protocol, what-if, or multi-schedule editors. A deeper
unification of scheduling logic would require a separate
behavioral design and regression effort. This release is not a
validation of medical PK model accuracy, serum levels, or dose advice.

## First guarded DEV qualification attempt (2026-11-15)

Candidate `deb41b563c9b18ccb09065f92633d0e92e64f228`
failed only after `3726` passing backend tests, at
`tests/test_pk_278_281.py::test_read_only_browser_smoke_contract`.
The Release 628 expansion of the existing read-only PK browser smoke
used Playwright `.click()` to open an optional `details` disclosure,
but the original Release 281 source contract intentionally forbids
both `.click(` and `.fill(` in the module.

Correction: the browser smoke now uses `summary.focus()` and
`summary.press("Enter")` to exercise the same accessible native
disclosure via keyboard, without clicking or filling application
controls. All original Release 281 required markers remain present.
The historical `tests/test_pk_278_281.py` is now in the focused
non-deploying regression gate, together with Release 628 source
contracts. The existing mandatory browser module is still wired in
the standard disposable Chromium gate.

This records a blocked pre-install qualification, **not** a successful
Release 628 deployment. The revised candidate requires another full
guarded DEV run.

## Operator-required qualification capacity (2026-11-15)

Backend qualification already used `pytest-xdist -n 16`, and
`scripts/tracker-release.sh` already launched the release-worker
systemd unit with `MemoryMax=16G`. The discrepancy was in the
browser qualification shell script: two initial Chromium batches used
four workers and the separate strict per-module runner used four
(full) or one (targeted). Release 628 now uses the same fixed
`-n 16 --dist=loadfile` everywhere in the browser qualifier.
The historical 594, 597, 598 and 627 source checks were updated to
validate the operator's new explicit 16-worker configuration instead
of asserting the obsolete four-worker limit. The 605 release-memory
contract remains unchanged.

Browser gates remain sequential at security-evidence boundaries:
some modules require signed mutation traces and immediate receipt
verification against shared disposable SQLite state. Parallelizing
their *invocations* as one test batch requires a separate race-safety
audit; 16 xdist workers for an individual small module may provide
little speedup and may consume more memory. This change satisfies
the requested worker configuration but does not falsely claim that
the full Chromium suite is now one batched pytest invocation.

The new candidate is not qualified until a fresh guarded DEV run
produces EXIT_STATUS=0. Never edit the installed runner or detached
worktree in place because the release expects a pinned immutable
candidate commit.

## Retry after Release 595 worker assertion (2026-11-15)

The next full backend attempt stopped after `3735` passing tests in
`tests/test_release595_food_vendor_lifecycle.py`, which still
asserted the obsolete four-worker browser runner count. Both this
test and the adjacent Release 596 source contract now check the
operator's sixteen-worker browser configuration.

To avoid repeating thousands of already passed backend tests on
routine UI releases, the five-release focused-testing cadence has
been brought forward to **Release 628 itself**, rather than waiting
for 629. This candidate's mandatory focused preflight includes
Release 595, Release 596, the PK UI contract, historic release safety
contracts and cadence policy tests, all with sixteen pytest workers.

Under the pinned Release 628 branch naming and no changes to
authentication, middleware, CSRF or route handlers, the runner
reports `QA_FULL_REQUIRED=0`. The complete browser and backend
suites are deferred until Release 630. Releases 630, 635, 640, ...
and security-sensitive backend edits remain full-gate releases.
The isolated source, static impact, backup/restore, runtime smoke,
code rollback, exact commit and 16 GiB memory limit are unchanged.

This is stage-level deferral, **not per-test historical success
memoization**. Previous logs without a full machine-readable
passed-node ledger do not support reliable individual test skipping
across candidate SHAs. The user explicitly authorized the
five-release regression cadence.

## Focused gate scope correction

The first implementation of the new five-release QA cadence still ran
nineteen historical CSRF witness, route-inventory and browser-runner
contracts as part of the supposedly focused preflight. This repeated
old security investigations during routine PK UI releases and caused
unnecessary delay. The mandatory focused gate has now been narrowed
to core release/backup/runtime source-safety contracts, current PK UI
coverage, the established read-only PK browser contract, and relevant
workflow regressions. Historical CSRF modules continue to exist in
the repository and remain collected by the comprehensive regression
suite on releases 630, 635, 640, etc., or when a security-sensitive
application change triggers full qualification.

The isolated change-impact check, source parsing, 16-worker execution,
16 GiB worker limit, verified backups/restores, runtime smoke and
rollback protections remain intact.

An in-flight systemd worker uses a copied runner from its original
candidate and cannot be accelerated by subsequent GitHub commits.
The reduced gate applies only to a newly pinned release attempt.
