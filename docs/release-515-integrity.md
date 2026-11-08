# Release 515 — grouped data-integrity corrections

Base: Release 514 `0b7cc0960d0b7fbff92c0f38d9db76c01a4cdfd3`.

## Fixes
- **Protocol form fields:** reject mismatched dynamic-array lengths rather than silently
  truncating via `zip()`. Reject NaN, positive/negative infinity, negative
  amount/frequency, excessive numeric values, unknown units and invalid frequency
  periods; preserve the existing "interval > 0" rule. A malformed preview or
  save fails before any plan rows are replaced. Horizon NaN/inf safely falls
  back to 12 weeks instead of entering persisted numeric/forecast state.
- **Secondary Food weekly HTML:** require exactly seven correctly attributed
  reports, consistent with the already-guarded weekly CSV route.
- **COA ORM:** eliminate shadowed, duplicate `linked_coas`, `linked_vials`,
  `all_coas`, and `all_vials` declarations while retaining the existing
  mapped relationships and deduplicating view semantics.

No schema, dependency, service, or authentication configuration changes.

## DEV qualification
GitHub is version control **only**. Do not run GitHub Actions or hosted tests.
Use the exact branch commit on the guarded DEV LXC release workflow. Require:
- isolated HTTP/HTTPS browser qualification;
- complete backend regression suite;
- backup/recovery drill against disposable restored data;
- runtime smoke and verified exit status 0.

Do not promote to main/PROD until those DEV checks pass. Release 516 may be
based on this candidate, but it is independently gated and should never
be included in a PROD promotion until individually DEV-qualified.
