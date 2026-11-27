# Release 806 — progress context and optimization
- Independent range, event, machine, repetition and lab filters survive edit/cancel/save/delete. Flash messages precede URL fragments; invalid edits roll back and return to the edit form. Destructive confirmations remain.
- Rolling averages use binary search for actual inclusive windows. Qualification compares the pinned baseline and candidate on identical synthetic data; this is not whole-page latency.
- Plateau requires all four weekly means to lie within a 0.5% latest-weight spread with >=3 readings per week; endpoint-only checks could mislabel an intervening excursion. Display weekly sample counts and latest date.
- Existing workspace-scoped progress data, manual markers, food/workout coverage, Google Tasks, time entry and inventory idempotency unchanged. No migrations, external AI or production deployment.
- This increment does not exhaust the requested cross-module optimization; no speculative global asset cleanup, clinical autofill or refactoring.
Acceptance: change Progress filters one at a time, edit/cancel/save/delete a measurement and verify context and flash. Review trend and weekly coverage.

## Shared workflow corrections
- Keep a single native POST submission lock for tracked forms; legacy fallback remains for explicit opt-outs/discard. Cancelled submit attempts release the lock, restore dirty state and permit retry. History restoration clears pending UI. HTMX retains its own lifecycle.
- Inventory Health uses only the explicit sortable/filterable table enhancement; redundant generic search is skipped when the first enhancer succeeds. Generic tables retain their existing fallback. Severity filter returns to the findings anchor; Review and Clear use the shared action style.
- Added offline browser coverage for submission retry, duplicate prevention, HTMX exclusions, and one-filter behavior at the supported viewport widths; added API coverage of progress context and invalid edit rollback.

## Integrated audit context
When event markers are enabled, the existing Progress page reads relevant existing change-audit records in the selected range, groups them by UTC audit date, and overlays recent date groups alongside manual markers. It excludes what-if protocols lacking explicit active snapshot evidence and actual intake events (not plan changes). Shows the last 12 audit dates, up to 8 labels each, and links the original audit history. No new records, dose inference, clinical attribution or live integration.

### Qualification correction
The initial scoped run reported 96 passing tests and three assertion failures. The offline inventory browser fixture now loads the actual filter stylesheet and exercises both independent search controls. Historical navigation and daily-intake tests now verify the canonical Inventory group and the existing pending/recorded split, including full pre-intake sorting and independently sorted recorded intake. No production application logic or deployment gates are changed by this correction; all scoped modules remain selected.
