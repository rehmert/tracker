# Release 696 — Unified everyday and inventory usability pass

Baseline: verified Release 695 installed on DEV and PROD
`3acdfbb8e1b2513786ff20859d25726433122d43`.
Candidate: `release/696-integrated-workflows`.

This **single release** combines the previously proposed work for Releases
696–697 (Workout, Food, Doses and Vitals) and Releases 701–702
(Inventory, Purchases, COAs and Labs). No separate 697, 701 or 702
installations are needed for the work described here.

## User-visible changes

- **Workout / Gym Mode**: the primary session-ending button is
  **Finish & Review**. The historical **Finish Workout** endpoint and
  button remain accessible via **Other finish option**, rather than
  competing for attention. Set logging, routines, timer and device behavior
  are unchanged. No workout is ever finished by opening the disclosure.
- **Food**: visible logging shortcuts and targets remain identical; long
  explanatory text becomes a labeled, accessible disclosure while the
  caution that missing nutrient data is unknown stays visible.
- **Doses**: a direct primary navigation to the existing vial confirmation
  when vials exist; without vials it links to the Vials inventory instead.
  Planned entries, repeat-draft cautions and the two-stage save flow
  remain unchanged, with extended help under a disclosure.
- **Vitals**: reading entry stays in place. Optional interpretation caveats,
  related insight pages and export shortcuts are in a disclosure.
- **Vials**: preserve all nine original routes and the exact legacy
  toolbar selector. Place three common actions first; six advanced
  destinations remain available via **More inventory tools**. The
  disclosure wraps instead of clipping on narrow phones.
- **Purchases**: place the exact existing New Order form above the long
  historical table, so first-time entry does not require a scroll.
  Keep the order-first-then-add-items notice and all filters, export,
  review, money fields and original submission safeguards.
- **COAs**: improve table readability, group primary/advanced navigation,
  and provide a **read-only, client-side** search of the certificates
  already displayed to this user. Never changes records, exposure,
  metadata or authorization; the existing compound GET filter remains.
- **Labs**: show existing saved Reports before the potentially long
  analyte trend cards, with direct anchor navigation to each; all
  prior search/sort and chart handlers remain unchanged.

## Release limits / backward compatibility

Changes affect only the nine existing HTML templates listed in the
preview allowlist, one new scoped shared stylesheet, and one new
read-only COA search script. The server, database models, migrations,
auth, CSRF, and all POST routes remain unchanged. Existing equipment,
nutrition, administration, test, certificate, supply and purchase data
are not edited or rewritten. The full legacy workflow remains
available even where a secondary action is behind a disclosure.

This is a focused interaction/layout pass, not a full redesign of
every internal editor or a large-scale CSS refactor. Visual regression
baseline automation and broader stylesheet consolidation are separate
future projects.

## Qualification

`scripts/tracker-release-scoped696.sh` runs Jinja, CSS and JavaScript
syntax checks; focused nine-page source contracts; read-only HTTP
renders; and selected historical Food, Workout, Inventory and Purchase
regressions. `scripts/tracker-preview696.sh` runs that gate in a
detached candidate worktree using temporary data and a local HTTP server,
then isolated Chromium checks at 320, 390 and 1280 pixels, including
the real Vials disclosure, New Order position, Lab report position and
COA search interaction. The preview does not install or deploy.

There is deliberately **no full suite on each release**. The guarded
DEV release runner repeats the scoped source gate and performs existing
release smoke checks. Production promotion requires exact DEV
qualification, successful DEV visual acceptance, signed approval and
the DEV-controlled PROD deploy process.
