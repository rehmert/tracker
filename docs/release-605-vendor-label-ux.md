# Release 605 — Vendor offer paging and single-vial label preview zoom

**Base:** Release 604, `62b5e624a488c794215d9834be558461e18752fd`.

## Changes

1. **Vendor Price Comparison:** Add 25/50/100/All client-side page sizes
   with Previous/Next buttons and a live visible-range indicator. Pager
   controls are hidden when all matching offers fit on one page.
   - Compound filtering resets to the first page.
   - Column sorting considers the complete underlying table (including
     currently hidden rows), then resets to page one.
   - Display continues to use the original rows, edit links, delete forms,
     shipment estimates and lowest-delivered-price badges.
   - Empty searches and the "no offers" placeholder are preserved.
   - No stored preference, extra network requests or new write paths.

2. **Individual Vial Labels:** Add the same screen-only 100–500% zoom control
   (300% default) already present on multi-vial label sheets. Reuse the
   existing Release 449 JavaScript and per-tab zoom preference. The preview
   retains horizontal scrolling at smaller widths. PNG/SVG export routes,
   underlying SVG dimensions, rotation, physical 203-DPI output and source
   records are unchanged. Print CSS disables preview zoom.

## Verification

- `tests/test_release605_vendor_label_ux.py` validates both Jinja templates,
  original write paths and export URLs, and runs actual Vendor Price Comparison
  JavaScript inside isolated headless Chromium at 320, 390 and 1024 px.
- The browser matrix tests initial 25-row paging, navigation, compound filter,
  reset, cross-page sort, All selection and label zoom changes.
- After source review, run the existing guarded **DEV** release runner from
  a clean installed Release 604 checkout against the exact branch HEAD.
  Require complete backend suite, strict HTTP/HTTPS browser checks, restore
  verification, deployed exact SHA and preserved root-only qualification log.
- Manually review Vendor Pricing and both individual/multi-vial label views
  on DEV. Do not use a printed label as evidence of hardware compatibility.
- After successful DEV qualification and manual review, use the existing
  DEV-controlled signed promotion preflight, then explicitly execute if
  approved. No automatic PROD deployment.

## Explicitly deferred

- Direct NIIMBOT B1 USB printing. The browser's Print button relies on a
  compatible local print driver, and direct USB access requires a separately
  reviewed host-side bridge, OS/USB transport discovery, paper-size mapping,
  fail-closed queueing, physical printer tests and an isolated authorization
  boundary. No printer discovery or direct-device calls were introduced.
- No database, schema, dependency, authentication or systemd changes.

## First DEV attempt — OOM termination and fail-closed remediation

The first guarded attempt from Release 604 to `23a33195f2ab7093ae5f09ac9086e358cd51fb0f`
passed source preflight, focused Release 604 regressions, regular browser and
strict CSRF HTTP/HTTPS browser gates. The full backend run (`-n 16`) was
killed at about 68% of progress. The transient systemd unit reported
`Failed with result 'oom-kill'` with a 3.1 GiB unit peak. The 8 GiB host
also reported full swap. The existing DEV checkout stayed at Release 604;
the release did **not** qualify, and no PROD promotion was made.

The previous exit handler emitted a misleading intermediate `EXIT_STATUS=0`
during cleanup even though the backend-pass marker was missing; the evidence
verifier correctly rejected the incomplete log. Candidate changes:

- Bound the complete backend suite to **4 pytest-xdist workers**. The full
  test inventory and canonical single pytest invocation are unchanged.
- Reduce transient worker `MemoryMax` from 6 GiB to **2 GiB** to fail
  within the disposable release unit under memory pressure rather than
  aggressively consuming host memory. This is conservative, not a promise
  that 2 GiB will always be sufficient.
- Register nonzero signal exits and mark the worker complete only *after*
  the restore, install, runtime smoke and deployment-success stages.
  Incomplete worker exits cannot be accepted as successful qualification.
- Run new 605 UI Chromium witnesses and the memory-guard source tests during
  the existing isolated focused regression **before** costly full browser
  and backend suites.

**Important bootstrap constraint:** The installed Release 604 launcher
copies its *own* on-disk `tracker-release.sh` into the transient worker.
Merely updating a newer runner on the GitHub Release 605 branch is not
sufficient: directly invoking the installed Release 604 launcher again
still uses `-n 16` and `MemoryMax=6G`. To qualify the new source safely,
the operator must first extract `scripts/tracker-release.sh` from the
exact pinned candidate Git tree into a root-owned private scratch directory
and check its Git blob hash and shell syntax, then invoke *that* candidate
runner against the clean, still-installed Release 604 baseline. The
candidate runner retains the same SHA guards, isolated tests, backup/restore,
signing separation and source-only install/rollback. Never patch the live
Release 604 installation or disable the existing gates.

The first attempt's tests were not complete. No post-OOM release success or
new evidence receipt may be claimed until the replacement exact-commit DEV
qualification finishes with `EXIT_STATUS=0` and the independent evidence
preserver accepts the complete log.
