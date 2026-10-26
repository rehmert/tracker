# Tracker v2.3 — Multi-compound PK overlay increment

Built on the preceding v2.3 Health Insights package.

## Features
- `GET /pk/overlay?compound_ids=1,2&days_back=30&days_forward=60` supports 1–4 supported compounds.
- Each compound's recorded administrations are modeled independently and normalized to its own maximum within the displayed time window.
- UI includes a multi-select control, common-time-axis chart, now marker, legend, and per-compound recorded administration counts.
- Rejects invalid identifiers, unsupported compounds, and invalid ranges.
- No schema changes; no writes to inventory, dosing, or scenarios.

## Interpretation
Normalization is **only** for comparing shapes and timing. The curves are not measured blood concentrations and cannot be compared as potency, efficacy, or safety across compounds. The chart excludes hypothetical future administrations.

## Validation
Run `python -m pytest -q` from the project root after installing development dependencies.
