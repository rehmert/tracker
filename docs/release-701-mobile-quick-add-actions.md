# Release 701 — Mobile Log sheet direct actions

Baseline: fully deployed Release 700
`405efb56dbf2c4a085149da8ba23fc1fd99729cf`.
Branch: `release/701-mobile-quick-add-actions`.

## User-visible change

On phones (<=760 px), the bottom **Log** dock opens the existing
`Quick Add` sheet. The sheet already offered fast forms for Weight,
Blood Pressure and Water, and shortcuts for Food, Dose, Labs and All
actions. Release 701 adds two missing direct links:

- **Log Workout Set** → `/workouts/quick` (the existing Gym Mode);
- **Log Supplements / Meds** → `/regimen#reg635-today` (the existing
  Today regimen section).

These destinations already exist on Today and Quick Entry. The change
makes the most frequently-used mobile Log affordance consistent without
creating a duplicate form, altering a recording transaction or changing
the actual underlying destination.

The sheet retains its two-column grid, 44px minimum tap targets,
full-width All actions link, focus-visible styles, responsive safe-area
padding and native keyboard navigation. On desktop, the Log link still
uses its existing `/quick-entry` fallback.

## Exact application scope

Only `app/templates/_mobile_quick528.html` changes in the application.
No CSS, JavaScript, backend/routes, database schema, authentication, CSRF,
write endpoints, data migrations or existing records are modified.
The three existing Quick Add forms remain unchanged, continue to submit
only through their original endpoints, and do not save on navigation.
Links are same-origin application paths.

The remaining new files are release-specific source/browser tests, a
detached DEV preview, a scoped qualification wrapper and this document.

## Guarded DEV qualification

`scripts/tracker-preview701.sh` requires:
- hostname `tracker-dev`, root under `systemd-run`, live DEV Tracker,
  a clean installed `main` checkout at the exact Release 700 baseline;
- an exact path allowlist, a source diff check and a release candidate
  that descends from the baseline;
- a detached candidate checkout in a private `/tmp` work directory,
  an empty disposable `TRACKER_DATA_DIR` and a browser-accessible
  loopback-only candidate server; trusted locally installed HTMX bytes
  are copied (verified) into the preview without downloads.

Scoped source tests check actual navigation paths against the matching
Today/Quick Entry templates, Jinja syntax, unchanged three form routes
and client-side security assumptions. The existing Release 528 focused
tests exercise Quick Add's previously established protected write routes
only in the **empty disposable database**; Release 695 direct navigation
source tests preserve the original destinations.

Playwright opens the actual `/mobile` page, rather than a mockup, for
4 widths (320, 390, 430, 760), 2 color schemes, and 3 layout densities:
**24 mobile layout configurations**. For each it checks that Log opens,
all six actionable links appear in the defined order, their touch
targets measure >=44px, the sheet fits the viewport horizontally,
existing Weight/BP/Water forms retain visibility isolation, Back and
Escape work, and no POST is generated. A desktop fallback check ensures
Log navigates to Quick Entry without opening a mobile dialog. External
asset requests are blocked in the browser.

No application-wide test suite is required for this single-template,
read-only navigation change. The isolated candidate never installs or
promotes; it cannot read the installed DEV or PROD database. A passing
preview permits the normal exact-SHA guarded DEV release; acceptance on
DEV and a signed DEV-controlled production promotion are separate
subsequent steps. No qualification or deployment success is claimed
before actual execution.
