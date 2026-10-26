# Tracker v2.3 — Health Insights Increment

Built on the previous v2.3 administration audit release.

## Included
- New read-only `/health-insights` page with a common 30/90/365/1095/all-day filter.
- Weight, systolic/diastolic blood pressure and pulse charts using existing SVG chart engine.
- Selectable lab analyte trend with existing unit-conversion and printed-reference-band behavior.
- Optional recorded dose/vial event markers; temporal proximity is not evidence of causation.
- Navigation entry and dashboard regression tests.

## Deployment
Integrate source into your Git development checkout, review diff, run `python -m pytest -q`, commit and deploy through GitHub. Do not overwrite `.env`, `data/`, `backups/`, or `/tracker-backups/`. No schema migration required.

## Validation
98 tests passed.
