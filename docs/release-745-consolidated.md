# Release 745 — Consolidated controller hardening, MACD and mobile CSS

Base: Release 744 at `0e9925532127eab2c939fb4ed5c045c6bf0dbe11`.
One source release ref: `release/745-macd-mobile-controller`.

## Release controller — host enforcement
The release includes a reviewed, pinned `scripts/tracker-release-agent745.py`
derived from the previously installed ops agent. Its root-owned local history
anchor saves the last accepted GitHub control-branch SHA. Before executing
a new command it walks **each intervening GitHub commit** and validates the
proposed transition against the predecessor's exact immutable receipt.
A stale safety-hold rollback, pending-request supersession, unknown live
stage or unapproved stage jump fails closed. Fresh failed qualification
requires a changed exact SHA; only a matching non-executed StageChainBlocked
retry can reuse the target. No stage is silently retried.

The guarded DEV installer verifies the existing host-agent Git object against
the pinned ops-control commit, validates the candidate agent object, installs
the source release through the normal guarded runner, then atomically replaces
the root-owned agent binary. It retains a single root-only pre-upgrade copy
under `/var/lib/tracker-release-agent/agent-before745.py` for manual recovery.
The running agent finishes the current stage using its already-loaded source.
Subsequent timer invocations load the installed new version. GitHub branch
writers can still push a bad commit, but the installed controller will reject
executing that unapproved history. No secrets or private logs enter GitHub.

## MACD — implement the remaining confirmed gap

Food Journal water entries had Add and Delete, but not correction. Release 745
adds a native Edit water disclosure for correcting ounces and/or recorded date.
The update checks original-day and record ID atomically; wrong-day, deleted,
malformed/oversized quantities and invalid dates fail closed. The original
entry ID and created_at remain unchanged. Delete now requests confirmation.
Existing Food macros/entries and other days remain untouched.

Regimen items, schedules and actual intakes already had scoped edit and guarded
archive/stop/delete (Releases 733–738). Workout routines, sets and equipment
already had add/edit/reorder and history-guarded delete (Releases 719, 739–740).
Supply, COA, Lab, Protocol, Calendar and Notes operations were reviewed in
Release 741. The Release 745 capability matrix consolidates the verified
existing actions and the new Water edit. No meaningless Move or unsafe
whole-blend deletion is invented.

## Mobile and CSS

Rapid Gym's five stylesheet requests collapse to one ordered, verbatim
concatenated CSS bundle, reducing four HTTP requests while preserving the
load-order cascade, existing source CSS files and normal workout JS.
Water corrections gain scoped 44px tap targets, responsive fields and
keyboard focus-visible outlines in the existing Food UX stylesheet.

## Qualification and deployment

Change-scoped, private-network exact-SHA checks include: code/shell
syntax and asset preflight; controller history/receipt transition tests,
water database/API correction and wrong-day denials; legacy Food/MACD
and coordination tests; Rapid Gym CSS byte parity and real Chromium
computed-style parity across 320/390/430/760/1024px light/dark layouts.
No full application regression suite, dependency update, global strict-CSRF
activation or schema migration. DEV is installed only after successful QA.
PROD promotion requires the normal signed, guarded DEV-controlled stages.
The permanent release-event PR #53 is notification only and is never merged.
