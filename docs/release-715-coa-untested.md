# Release 715 — COA endotoxin result defaults to Untested

**Base:** Release 714, `247f413d46f9f1b635144c7f141a57027fd26449`

## Intent

A default of `<1 EU/vial` represents a laboratory finding, not an unknown
test result. It must never be inferred simply because the user entered a
certificate of analysis or left the endotoxin fields untouched.

All three COA create/edit endpoints and both user-facing create surfaces now
default the **Endotoxin result (EU/vial)** selection to `Untested`.

Accepted choices:
- **Untested** (new default): explicit `endotoxin_result_kind="untested"`,
  `endotoxin_eu_per_vial=NULL`. No evidence of an endotoxin result is implied.
- **<1 EU/vial**: explicit `"lt1"`, numeric `NULL`; only when the lab reported it.
- **Exact numeric result**: `"exact"` with a required finite nonnegative
  `endotoxin_eu_per_vial` (including a real, reported zero).

Existing stored `lt1` and `exact` entries are preserved on view/edit;
historical `NULL` statuses are displayed as Untested but not silently
backfilled until explicitly saved. No migration or mass data update occurs.

A form that submits `Untested` alongside a nonempty numeric value is rejected
without mutation. This prevents accidentally discarding an actual recorded
measurement when switching a previously exact result to Untested; the user
clears the old exact number first. Existing historical percent fields remain
untouched and must never be reinterpreted as EU/vial.

This change is confined to the **endotoxin result** field. It does not change
COA review/verification status, test-type catalog entries, document uploads,
vial links, or laboratory results.

## Qualification

`scripts/tracker-qualify715.sh` uses a pinned exact Git commit, a detached
source worktree, `PrivateNetwork=yes` and a disposable SQLite database.
Changed paths are individually allowlisted; no installed DEV mutations
occur during qualification.

The scoped test gate includes:
- New/legacy COA form defaults, API validation and numeric preservation
- Existing Release 645 endotoxin and historical migration regressions
- Multiple-document and COA manager lifecycle compatibility
- Strict-CSRF Chromium HTTP and HTTPS create, edit, explicit result
  transitions, and vial-level create-form default
- Isolated browser test catalog/targeted-mode registration
- Minimal syntax/import, release asset-impact preflight and runner gates

Only these impacted tests run, not the entire application test suite.
The qualified exact SHA may then be installed on DEV using
`scripts/tracker-install715.sh`. PROD promotion requires separate explicit
user authorization and read-only preflight, with scoped PROD checks.

**No schema change. No production change without explicit approval.**
