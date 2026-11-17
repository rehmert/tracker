# Release 673 — Integrated Mobile UX

Baseline: Release 672, `3ccf5cd4b3ab268ae8db8e2a795dc70ab13a642b`.
Branch: `release/673-integrated-mobile-ux`.
Single consolidated release for the four proposed mobile initiatives.
No database or API migration.

## Implemented

1. **Shared mobile design layer** (`tracker-mobile-ux673.css`): common spacing
   variables, desktop-compatible editor action rows, 44px touch targets,
   five-destination mobile dock and opt-in mobile record-card tables. Supports
   all three existing display densities; desktop behavior remains unchanged.
2. **Mobile management cards**: COA and Supplies tables become labeled
   two-column cards at phone widths without duplicating underlying DOM,
   with all existing links, use forms, filter hooks, sort data and HTML table
   semantics preserved in source. Purchases retains its preexisting
   user-selectable card/table mode and adds explicit cell labels for clarity.
   The complex Vial bulk-edit grid remains a scrolling table to avoid
   breaking sorting and multi-select operations.
3. **Food Journal**: a four-action primary grid for Log Food,
   Scan/Add, Log Water, Today's Meals; configuration and analytics navigation
   moved into a single labeled More Food Tools & Analysis disclosure.
   Original sections, IDs, forms, search, data completeness and links remain.
4. **Mobile dock**: five destinations (Home, Today, Log, Workout, More);
   existing quick-add sheet retains its original trigger ID and behavior.
   Doses/Vitals remain accessible through Today, the Log flow, and sidebar.
5. **Rapid Gym**: active set entry and rest timer remain available;
   less-frequently used offline/draft controls and secondary workout
   destinations move into accessible disclosures. No change to set saving,
   queuing, syncing, workout finishing or machine configuration.
6. **Common action rows**: apply consistent styling in saved food and
   compound editors without changing form methods or destinations.

## Deliberate limitations

- These changes do not rewrite every historical feature stylesheet. A scoped
  shared layer is safer than deleting old CSS that may contain required
  feature-specific behavior.
- Detailed Vials bulk-edit and analytical tables are intentionally left
  horizontally scrollable on phones.
- Visual regression uses a disposable Chromium DOM/CSS fixture for widths
  320, 390 and 430 px and source/route contracts. No claim is made that this
  is a full production browser walkthrough on every route.
- Purchase card/table toggling, Food section autoexpansion,
  mobile quick-add behavior and Workout offline queue remain supported.

## Qualification and release gating

`scripts/tracker-preview673.sh` qualifies an isolated worktree and never
installs it. `scripts/tracker-release-scoped673.sh` runs Jinja parsing,
Python syntax, targeted existing regression tests for the shared mobile shell,
Food Journal, purchases, supplies, and workouts, plus the new mobile CSS and
interaction tests in disposable Chromium at phone widths.
It deliberately does not run the entire Tracker application suite.

`scripts/tracker-release673.sh` requires explicit readiness approval
and performs signed DEV-controlled promotion with exact baseline and
commit checks. PROD runs the focused gate before installation.
