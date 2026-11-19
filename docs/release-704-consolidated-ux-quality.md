# Release 704 — Consolidated mobile UX and quality milestone

**Baseline:** Release 703 verified installed DEV and PROD at
`17e7a68daf8cb9a0c6219b162a54b9e7a1b9f8e2`.
**Candidate:** `release/704-consolidated-ux-quality`.

## One-release plan (no Release 705–709 UX rollout)

This deliberately combines the next five **usability, accessibility,
presentation consistency, regression coverage, and observational quality**
increments into **one candidate, one guarded DEV install and one
signed DEV-controlled PROD promotion**. It is not a claim to have
independently certified every screen in the application.

### 1. Remaining long-edit workflows

Five heavily used edit/entry forms receive one reusable mobile-only action
treatment (`tracker-edit-actions704`) while retaining **exactly their
original** buttons, links, native POSTs and business validation:

| Workflow | Original action preserved | Secondary behavior |
| --- | --- | --- |
| Dose correction | Save entry / Cancel | Same vial-scope, disposable corrections, journal history and final review |
| Notes editor | Save page / Cancel | Discard local draft remains a type=button with its existing recovery and confirmation |
| Log Previous Workout | Save Completed Workout / Cancel | Existing CSV import form, dynamic rows, routine and session history unchanged |
| Preparation correction | Save correction / Cancel | Existing supply reconciliation and vial destination unchanged |
| Manual lab report | Save report / Cancel | Existing Add row remains in the manual form immediately above actions, and separate CSV import remains independent |

The original Save/Cancel pair remains **inside the same form**: no
duplicate submit actions, no fake button links, no submission rerouting,
no new record types or server changes. The action region on phones
(<=760px) uses two keyboard-accessible, 48px+ controls in a theme-aware,
safe-area-aware sticky panel positioned above Tracker's existing bottom
dock. It reverts to natural document flow while an input has focus,
matching the dock's keyboard behavior. Notes' third Discard action
stays in DOM/Tab order and occupies a full row at narrow widths.
Desktop >760px keeps its prior layout, and print disables stickiness.

### 2. Better native-invalid feedback

The new `tracker-edit-feedback704.js` **only observes** the browser's
native `invalid`, `input` and `change` events on these five forms. If
the browser finds an invalid field, one role=alert message asks users
to review the highlighted field(s); it disappears after all fields
become valid. It **does not** mutate values, prevent submission, call
fetch, use storage, redirect, bypass application validation or record
anything. Existing server-side validation and error states remain the
source of truth. No confirmation dialogs or new error branches are added.

### 3. Shared presentation and responsive check

The five opt-in templates reuse a **single shared** new CSS file instead
of copying the previous 702/703 rules into five more page stylesheets.
Historical Saved Food, Vitals and Compound editor CSS rules from Releases
702/703 remain untouched, since changing their tested cascade would risk
a visual regression. Release 704 consolidates **new work**, not every
historical CSS file. A later wholesale CSS deletion is not included or
promised.

### 4. One milestone browser and visual gate

All tests operate in a detached candidate checkout with empty private
SQLite data, not the installed DEV or PROD database.

- Real Jinja templates, synthetic populated examples (dose, notes,
  workout machine and set, preparation, and lab manual) rendered in
  Chromium, no app server in that fixture and **no HTTP writes**.
- 5 forms × 5 widths (320/390/430/760/1024) × 3 densities
  (Compact/Balanced/Comfortable) × 2 themes = **150 configurations**,
  with form containment, correct existing endpoints, Save→Cancel tab
  order, 44px+ controls, no horizontal overflow, sticky/dock clearance,
  and keyboard-induced nonsticky behavior.
- Native-invalid browser event, explicit one-form/one-save test,
  and readable role=alert feedback; original CSV import and auxiliary
  controls are checked for preservation.
- The previously qualified 702/703 mobile browser matrices plus
  the 603 dock-pointer and 673 integrated mobile regressions.
- Original Release 698 **136-image real-page visual gate** on two
  isolated servers and independent empty databases, comparing
  ten top-level pages against the exact Release 703 baseline.
  This covers regressions to unaffected pages, not intentional edit
  page visuals that require **DEV visual acceptance**.
- Existing dose correction, historical workout atomicity,
  lab import/review, source layout, Vitals/Compound form contracts and
  other focused API regressions in isolated SQLite.
- As a consolidated milestone, explicitly run the existing **full
  preproduction DEV suite** with the established
  `tracker-release.sh --full-suite` approval **after** the fast isolated
  preview, not on every small edit and not by default on PROD.

The standard installed guarded runner continues to handle rollback,
snapshot verification, health checks, DEV qualification evidence and
signed DEV-controlled PROD promotion. **No special release path.**

### 5. Whole-repository inventory and measured performance baseline

`scripts/tracker-ux-audit704.py` is a static **read-only** inventory
of source templates, POST/GET form declarations, buttons, links and CSS
files. It reports the five improved editors and three earlier mobile
editors. Its counts may differ from runtime form counts because of
Jinja loops and conditionals: it is **not** a runtime completeness or
security certification.

`scripts/tracker-latency704.py` performs **only HTTP GET** against
an explicit `http://127.0.0.1:PORT` local disposable server. It collects
three non-cached requests each for ten core pages, and reports per-page
median response time. Redirects, credentials, arbitrary paths, public
hosts and proxies are denied. This is **measurement**, not an
unsubstantiated claim of a database optimization; it cannot establish
end-user speed or a query N+1 without further profiling.

### Explicit security and reproducibility boundaries

**Open issue #9 (strict CSRF):** legacy and multipart browser negative
cases are not globally certified. This candidate does **not** change
`TRACKER_CSRF_ENFORCE`, authentication, signing, Origin checks, middleware,
POST handlers or CSRF routes. Turning strict mode on without evidence
could break valid production data entry. Issue #9 remains open.

**Open issue #10 (dependency reproducibility):** existing Release 569
observed constraints are still not a fully hash-locked wheelhouse with a
recreated Python 3.13 environment and verified Chromium/OS libraries.
No dependency upgrade, pin changes, lockfile claims, package download or
live Python environment changes occur here. Issue #10 remains open.

These two security/infrastructure projects are NOT silently treated as
completed by a UX release. If a single all-issues production deployment
is required, do not promote Release 704 until separate, independently
reviewed strict-CSRF and reproducibility evidence is gathered and the
candidate is revised with a newly qualified exact SHA.

## Fail-closed scope

14 paths: five HTML templates, two new scoped CSS/JS assets, two
read-only inventory/latency scripts, two source/browser test modules,
two isolated qualification scripts, and this document. No changed
routers, auth, middleware, database, schema, migrations, existing JS
guards, requirements or environment files.

`scripts/tracker-preview704.sh` checks root systemd execution on
`tracker-dev`, clean installed Release 703 main, exact branch ancestry
and strict 14-path allowlist; creates two detached worktrees and
separate empty private data directories; runs focused source and
browser tests, real-page Release 698 visual comparison and
read-only latency. It never installs, pushes, approves or promotes.
Private synthetic screenshot diffs, when any, remain on DEV and are
not uploaded to GitHub.

**Qualification is not complete merely because these instructions
exist.** Require explicit preview markers, full DEV milestone gate,
manual visual review, PROD dry-run and signed operator authorization.
