# Release 698 — Automated visual regression gate

Baseline: Release 696, deployed and verified on DEV and PROD at
`6af8e4185fc76212f05d8a53cd4fec4043d804eb`.
Candidate branch: `release/698-visual-regression`.

This is a **tooling-only** release: no application templates, stylesheets,
database schema, user routes, authentication, save flows or production data
are modified.

## What the gate actually compares

`scripts/tracker-preview698.sh` checks out **both** pinned Release 696 and
the candidate into separate temporary worktrees. It launches two loopback-only
Tracker instances with **separate, empty, disposable SQLite data directories**,
each identified as DEV. It does not touch the installed DEV service or any
live user records and performs no writes to production.

`scripts/tracker_visual_regression698.py` opens the same page on both
servers in the **same** local Chromium browser, using clean contexts with
identical theme preferences. It checks the actual reported HTML theme is
light/dark; both copies must have the same page heading, main width and no
additional horizontal overflow. Viewport screenshot image pixels are compared
with Pillow; grayscale pixel differences of 28 or more are counted, and
a **1.2%** changed-pixel threshold raises a failure.

Capture matrix:

- **10 pages:** Overview, Today, Food, Doses, Vitals, Gym Mode, Vials,
  Purchases, COAs, Labs
- **4 viewports:** 320×844, 390×844, 768×900, 1280×900
- **2 themes:** light/dark, verified from the actual rendered HTML
- **Details:** additional anchored screenshots on Food, Doses, Vitals,
  Vials, Purchases, COAs, and Labs

At least 80 top-of-page baseline comparisons are required, plus matched
anchor screenshots when those sections exist. Assertions also block
changes to the page title or main width and increased horizontal overflow.
No per-page exceptions or auto-approval mechanism silently accepts changes.

This is **not** a golden-image repository. Images are computed from the exact
release baseline in a disposable installation and compared with candidate
images. Therefore they are particularly useful when a proposed code change
is meant to be nonvisual. For intentional future UI changes, a visual
difference is a review finding requiring explicit acceptance and an updated,
documented baseline; do not bypass or silently raise the threshold.

## Privacy / failure artifacts

Only empty-data fixtures are rendered. The runner refuses non-loopback
origins, storage-state credentials, and alternate schemes; browser request
routing also **aborts any outbound HTTP(S) resource** not directed to
one of the two isolated localhost server ports. No screenshots
or cookies are committed, uploaded, or sent through GitHub. The comparison
worktree, temporary data and screenshots are removed after success.

When a pixel mismatch is found, before cleanup the root-only preview
creates a private `/tmp/tracker-visual698-review.*` directory (0700)
containing *only mismatched cases*: baseline image, candidate image and
difference image (0600). The path is printed. Do not publish even
these synthetic screenshots without inspecting them. If a different
failure occurs, logs are displayed and no screenshots are fabricated.

## Qualification

The release-scoped source gate checks shell and Python syntax, isolated
loopback restrictions, Pillow pixel mismatch math, failure artifact
permissions, preview baselines and actual Chromium fixture styles from
Release 679. It has no downloads and does not run the full app suite.

The independent preview additionally runs the real dual-server visual
browser gate. The guarded DEV install will repeat the scoped source gate
and the standard readiness and navigation smoke tests. The installed
source contains the new tooling, not a background daemon or scheduled
capture task. Operator visual acceptance on DEV remains necessary before
the signed DEV-controlled production promotion.

## Limitations

The comparison sees the first viewport plus selected anchored sections,
not every screen position or state; interactions behind modal dialogs
and populated real-world tables are not exhaustively inspected. The 1.2%
threshold may miss a small isolated cosmetic change. The test does not
replace accessible control/behavior tests, visual inspection, or a future
reviewed golden baseline process. Its two generated databases start
empty; production content is never used for screenshot comparisons.
