# Release 616 — bundled workflow improvements (614–616)

**Base**: production-verified Release 613,
`7a2a6a593085876550cf5e5b991c32563be7d84c`.

The originally proposed Release 614, 615 and 616 workstreams have
been grouped into **one guarded Release 616 candidate** to reduce
qualification and promotion cycles. Numbers 614 and 615 are workstream
labels within this bundle, not separately deployed releases.

## 614: Read-only consolidated administration timeline

The Dose Log now has a chronological list of the latest 60 individual-vial
records and 60 blend draws, combined and sorted by actual timestamp.
The list has GET-only date, source (individual vial or prepared blend) and
type (administered or discarded) filters. Filters apply to those bounded
recent records; the display explicitly discloses this limit. A physical
blend draw occupies one row; constituents are displayed as context.
The original vial History with HTMX mutation target and edit/delete links
and the original blend history remain available below; no duplicate
inventory or DoseLog writes.

## 615: Calendar-to-record review

Matched and unmatched actual Calendar entries link to the unified Dose
Log timeline with the entry's compound and date preselected. Existing
direct source-blend links remain. Calendar reconciliation remains
same-day/same-compound only; no dose or clinical validation is claimed.

## 616: Inventory Health review

The Inventory Health report offers an optional severity filter (all,
errors, warnings) while retaining total counts from all findings.
It adds explicit navigation to the existing audit history, inventory
alerts, vial inventory and supply reconciliation. The diagnosis and
inventory datasets and all mutation endpoints remain unchanged.

## Safety and acceptance

- No schema migration, write-route change, new background task, auth
  change, global CSRF policy change or dependency change.
- The integration tests in
  `tests/test_release616_workflow_bundle.py` cover combined blend
  display, date/source/type filtering, real Calendar links, inventory
  report filtering, template parse and preserved HTMX target.
- Run the guarded DEV runner with its complete backend suite, isolated
  Chromium HTTP/HTTPS and strict-CSRF gates, backup/restore verification.
  Keep `-n 16 --dist=loadfile` and systemd `MemoryMax=16G`.
- After successful DEV qualification and visual acceptance, run the
  non-deploying signed promotion preflight; use explicit `--execute`
  for PROD only after approval.

## Next bundle: workstreams 617–619

Prepare only after this bundle is qualified and deployed:

- 617: extend read-only search and saved filter views, with explicit
  scope/permission tests.
- 618: guided purchase, blend and protocol review workflows using
  existing write validation and idempotency; no direct save bypass.
- 619: independently gated strict-CSRF compatibility work and dependency
  reproducibility investigations. Never globally enable strict CSRF or
  alter installed dependency versions as an incidental UI release.
  Issue #9 and issue #10 remain open until separate acceptance.
