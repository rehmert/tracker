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
