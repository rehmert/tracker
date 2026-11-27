# Release 806 — progress context and optimization
- Independent range, event, machine, repetition and lab filters survive edit/cancel/save/delete. Flash messages precede URL fragments; invalid edits roll back and return to the edit form. Destructive confirmations remain.
- Rolling averages use binary search for actual inclusive windows. Qualification compares the pinned baseline and candidate on identical synthetic data; this is not whole-page latency.
- Plateau requires all four weekly means to lie within a 0.5% latest-weight spread with >=3 readings per week; endpoint-only checks could mislabel an intervening excursion. Display weekly sample counts and latest date.
- Existing workspace-scoped progress data, manual markers, food/workout coverage, Google Tasks, time entry and inventory idempotency unchanged. No migrations, external AI or production deployment.
- This increment does not exhaust the requested cross-module optimization; no speculative global asset cleanup, clinical autofill or refactoring.
Acceptance: change Progress filters one at a time, edit/cancel/save/delete a measurement and verify context and flash. Review trend and weekly coverage.
