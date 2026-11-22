# Release 747 — Final acceptance and maintenance handoff

Baseline: DEV and PROD Release 746, SHA c61a2a85f10d7b585f9edc1d62d756605e046c32.
Release 747 is an acceptance hardening release, not a speculative CSS refactor.

## Previously delivered; do not re-propose

- 745–746 global and Rapid Gym CSS bundles, mobile touch controls, and light/dark browser style parity.
- Existing Regimen, Workout, Food/Water, Supply, Vial/Blend, COA, Labs, Protocol, Calendar and Notes MACD where meaningful.
- Signed session and Origin guards, optional global strict CSRF, dependency pins and guarded DEV-first receipt-based release controller.

## Final automated acceptance

- Test actual signed HTTP/HTTPS Notes Add/Edit/History/Delete, Workout equipment Add, and Regimen catalog Add with missing/forged CSRF negatives.
- Verify signed cross-origin requests still fail and run existing all-registered unsafe-route negatives.
- Re-run existing strict multipart, session login, Food/Workout/Regimen MACD, mobile/Chromium and dependency regressions.
- Confirm installed DEV 44-package observed baseline read-only and no package change.
- Preserve synthetic-only test records, private receipts and release-event PR workflow.

## External blockers — cannot honestly be certified by source tests

- #9: Global strict-CSRF positive HTTP/HTTPS native/JS/HTMX/multipart tests and manual session-account/rollback review.
- #10: Independently approved full offline browser/OS dependencies and actual tested rollback on hosts.
- #54: User real-phone gym, keyboard and other mobile workflow acceptance.
- #56: Actual distinct-account owner-scoped end-to-end MACD with history, deletion and authorization across all record types.

These remain acceptance/approval items, not reasons for endless refactors. Do not close them without evidence.
No CSRF environment flag, installed package, user data or multiuser cutover is changed here.
Any confirmed regression should be fixed as a targeted new change, not another speculative cosmetics release.

REAL_PHONE_ACCEPTANCE=OUTSTANDING
OS_BROWSER_ROLLBACK=OUTSTANDING
GLOBAL_STRICT_CSRF=NOT_ENABLED
MULTIUSER_PARITY=NOT_CERTIFIED
PROD_REQUIRES_EXPLICIT_AUTHORIZATION
