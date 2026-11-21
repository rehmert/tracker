# Release 741 — One integrated MACD + mobile usability increment

Baseline: DEV and PROD Release 740 exact
`78de7168566f15dcd450ee24d7f2e8fe0cdae756`.
Scope: priorities 1–4 requested together, not four separate releases.
No schema migration, dependency change, release-agent change or automatic PROD action.

## Priority 1 — Supplies / inventory MACD

- Edit Supply in place: name, notes, and context-safe compound/category reassignment.
  Purchased/remaining quantities, unit-price and purchase association cannot
  be overwritten by a metadata edit.
- Changing a category is allowed only for **unused** stock with exactly the
  same unit and never to/from the special pill/BAC-water kinds.
- Stock with usage or reconciliation history permits name/notes correction,
  not compound reassignment or category conversion.
- Use immutable SHA-256 record state, SQLite inventory write lock, private
  before/after audit and transactional commit for Supply changes and deletion.
- Delete only unused, never-reconciled Supply purchase lines with explicit
  confirmation; both POST and UI enforce the dependency rule. The Purchase
  record and prior audit remain; removing an accidental supply line changes
  its purchase's line-item subtotal. Historical use is never deleted.
- Custom category rename and unit edits, but unit only when no stock exists.
  Reject changes/deletion of built-ins, and deletion of referenced categories.
  Private audit and optimistic version protect custom category edits/deletion.
- Use existing `/reconciliation` stock count workflow for physical correction
  (expected balance, reason, confirmation, write lock and audit).
  Use purchase detail for price/cost changes, not inventory meta-edit forms.

## Priority 2 — COA, vial, prepared blend and Lab record actions

- COA list: visible Edit, Document, Vial Link destinations; COA detail:
  anchored Edit, documents/default-test types, vial links and Delete.
  Existing upload/verification/assignment/dependency rules remain.
- Vials: direct Edit shortcut on inventory rows and a management bar on vial
  detail; preserve existing reconstitution, stock and COA edit/delete routes.
- Prepared blends: navigate to source-vial composition, standard logging and
  audited withdrawal correction/delete; **no whole-blend Delete** because
  a prepared blend records transfers of source inventory.
- Lab reports: row-level Edit/Results/Delete navigation, details page anchors.
  Existing result edit and deletion, report import/correction and provenance
  remain unchanged. No cross-owner reassignment or hidden new delete endpoint.

## Priority 3 — Protocol, calendar, Notes

- Protocol list exposes Edit schedule, Duplicate, Stop/Activate and guarded
  Delete native POST actions alongside the record; existing route logic
  remains the sole writer.
- Planned Calendar events include their source protocol ID as *display-only*
  provenance; review-list and event-card actions link directly to Edit
  Schedule without rewriting recorded administrations or exclusions.
- Calendar shortcut navigation and Restore hidden projections remain intact.
- Notes list exposes direct Edit, History and confirmed Delete actions.
  Deletion creates a private metadata-only ChangeAudit: the intentionally
  deleted note body is not copied into that audit. Existing source relations
  follow the old deletion semantics; Notes editor is unchanged.

## Priority 4 — Mobile UX

- One strictly scoped stylesheet `tracker-integrated-macd741.css` provides
  consistent Add/Edit/Delete/Manage target treatment for all affected pages:
  >=44px controls, >=48px on phones, visible native chevrons, keyboard focus,
  320/390/430px viewports and light/dark color preferences.
- Avoid rewrite of global CSS, changes to Rapid Gym density, or new scripts.
  Keep existing page-specific CSS in its original cascade order.
- This is an integrated cleanup, **not** blanket retirement of all 144 legacy
  CSS files; broader CSS debt remains separately measurable.

## Safety and qualification

- Per-user scoped DB, inventory write reservation, immutable request state,
  FK-protected writes, private audit, usage/reconciliation guards.
- Read-only Release 604 asset-impact preflight; branch ancestry, clean
  Release 740 DEV baseline and changed-file allowlist.
- Disposable SQLite with foreign keys ON; new API/DB negative cases,
  Notes audit checks, template syntax/route assertions; targeted existing
  stock/COA/vial/lab/protocol/calendar/notes regressions and Playwright
  320/390/430/760/1024 light/dark controls. No raw logs or user data on
  GitHub.
- DEV install only if qualification passes, pinned to one exact candidate SHA.
  PROD preflight/deployment require a fresh explicit operator authorization.

## Follow-up / non-goals

This release brings the four priorities into one DEV artifact and surfaces
their main existing workflows; it does not certify every possible record type
in every module as fully MACD-complete. Further use-driven fixes and global
CSS consolidation can follow based on actual phone testing.
