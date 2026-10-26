# Manual disposable selection for dose and preparation events

- Dose log: expand **Disposables used**, check the actual supply stock entries and enter quantities. Stock is deducted only when the dose is successfully recorded. Each deduction links to its dose via `supply_usages.dose_id`.
- Reconstitution: on a vial detail page, select optional disposable stock entries and quantities while recording the reconstitution. The existing BAC water stock selector remains available. Avoid selecting BAC water twice; combined stock use is validated.
- Filtering: on a vial detail page, expand **Record a filtering/preparation event**, select supplies and submit. Filtering is independent of dosing and does not change medication contents.
- Preparation events are stored in new `preparation_events` and `preparation_supplies` tables; startup `create_all` creates these non-destructively. Individual deductions remain in `supply_usages`.
- Deleting a dose returns linked disposable quantities to inventory. Editing a dose leaves its associated supplies unchanged. Preparation event history is shown on the vial page; there is not yet an edit/delete control for preparation events.
- Count-unit categories require whole-number consumption; other units allow fractional quantities. Inventory availability is checked before deductions.
- This is a manual recordkeeping feature. No automatic disposable selection or consumption occurs.

## Deployment
Back up your database and attachments. Deploy updated files without replacing `.env`, `data/` or uploads; restart `tracker.service`. New tables are created on startup. Hard-refresh the browser.
