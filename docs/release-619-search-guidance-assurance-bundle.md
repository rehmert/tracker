# Release 619 — bundled 617–619 workflow candidate

**Verified installed base:** Release 616, `3d6590af034de7bd44910fbd540dd21d985cc36b`.

This is a single Release **619** candidate, bundling workstreams 617,
618, and 619. Releases 617 and 618 are not independently deployed.

## 617 — bookmarkable Notes views

Notes gains the named URL views `/pages?view=all`,
`/pages?view=with-sources`, and `/pages?view=without-sources`
("Needs sources"). Each combines with existing Notes text, tag and
compound filtering. Invalid view values fall back to all. These are
bookmarkable URL-based presets, **not** database-stored saved searches
or global full-text search. No schema, user data or Notes writes change.

## 618 — guided review handoffs

The existing purchase, blend and protocol pages each gain a short
expandable review checklist with deep links to relevant inventory,
Calendar, purchase and source-vial pages. These are navigation guides,
not new transaction wizards. The established forms, preview,
confirmation, idempotency, CSRF enforcement and inventory mutation paths
are untouched. The UI clearly distinguishes previews and purchase
headers from completed inventory changes.

## 619 — security and reproducibility verification

Isolated regression tests assert that the existing global strict-CSRF
environment default remains opt-in and verify that the observed
Python/SQLite/package manifest agrees with the checked-in candidate
constraints. Focused qualification adds these checks. Full
backend/browser strict-CSRF acceptance is still mandatory in the
guarded release runner. This release does **not** enable globally strict
CSRF on DEV/PROD, install dependencies, upgrade packages, generate a
new lockfile, or close GitHub issues #9 and #10.

Operators may separately inspect DEV dependency drift with the
existing, read-only diagnostic:

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_dependency_baseline569.py --instance DEV
```

Do not use a static baseline assertion to claim fresh-environment
reproducibility: issue #10 requires an independently successful
disposable fresh-install replay, and issue #9 requires comprehensive
compatibility qualification before any global policy change.

## Guarded acceptance

- Full DEV release test workflow: backend `-n 16 --dist=loadfile`,
  isolated HTTP and HTTPS browser tests (including strict-CSRF),
  recovery-archive verification and post-install smoke checks.
- Preserve the original **interactive** guarded runner and the systemd
  `MemoryMax=16G` contract. No detached launcher.
- Only after DEV qualification and manual browser review, run the
  DEV-controlled **non-deploying** signed promotion preflight.
- Promote to PROD only with explicit `--execute`; a failed qualification
  is never approvable. No direct PROD deployment.
