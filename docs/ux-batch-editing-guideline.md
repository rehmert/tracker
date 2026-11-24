# Tracker UX guideline — batch-edit related fields

When users can edit several related fields on the same page, **default to a
single Save all action** instead of requiring a separate save for each row.
This is especially important for mobile and repeated data-entry workflows.

- Permit several edits before saving, without unnecessary navigation/reloads.
- Use one understandable primary save action, reachable near the beginning
  and end of long forms when helpful; both submit the **same** form.
- Validate the complete submission **before** persisting anything. Commit the
  group atomically, and clearly report errors instead of partially applying it.
- Preserve any unrelated fields, existing entities, identities and history.
- Allow blank optional fields to restore defaults if their semantics support it.
- Guard against stale views and unknown, duplicated or forged record IDs.
- Keep independently destructive or immediate actions (such as Exclude/Delete)
  separate; communicate that they should not be mixed with unsaved edits.
- Provide targeted automated coverage for multiple edits, no-op saving,
  validation rollback, stale forms and mobile-friendly markup.

Apply this guideline to future Tracker feature changes unless users explicitly
need independent per-row transactions (for example, rapidly logging a set).
