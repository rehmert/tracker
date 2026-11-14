# Release 611 — Blend administration visibility and calendar handoff

Base: fully qualified Release 609
`88d5ca98841642502d704e96e39f8c9cf1dda41b`.
Release 610 is **on hold** and is intentionally not included.

## Bug identified

A draw recorded under Blends is a `BlendDose`, while Calendar
reconciliation and the primary Dose Log previously read only ordinary
`DoseLog` records linked to individual vials. Thus, a recorded blend
administration could be visible on the blend detail screen but absent from
both Calendar and Dose Log. The Calendar → Doses → Blend selector also
discarded the calendar-selected timestamp.

## Fix

- Display recent blend draws as a separate, clearly labeled section of
  the Dose Log (administered and discarded, one row per physical draw,
  including calculated constituent amounts and link to the blend).
- When the Dose Log is filtered by compound, include only blended draws
  containing that compound. Do not fabricate individual source-vial doses.
- Include administered blend draws in Calendar reconciliation, with one
  same-day contribution per distinct constituent compound. Match each
  projected occurrence to at most one actual logged administration.
  Blend waste is **not** an administration and never satisfies a plan.
  These are record matches by day/compound, not verification of amount
  or clinical appropriateness.
- From Calendar → Log this dose → choose an active blend containing the
  scheduled compound, preserve selected local date and time on the blend
  entry form, and return to the selected calendar date on successful
  submission.
- Reuse the existing BlendDose endpoint, inventory reservation,
  idempotency and audit. No schema migration, duplicate inventory debit,
  change in global CSRF, or new write route.

## Qualification

`tests/test_release611_blend_calendar.py` exercises the real blend POST
and read-only calendar/history paths: recorded vs waste, no duplicate
DoseLogs, exact constituent calculations, selected date/time and return
location. Included in the early focused gate. Still require the full
guarded DEV browser/backend suite, backup/restore verification,
qualified receipt and manual UI review before signed PROD promotion.

Backend pytest remains 16 workers; worker MemoryMax remains 16 GiB.

## Release ordering

Because Release 610 was intentionally held on a branch from 609,
this 611 hotfix also branches from 609. When resuming the optional
Release 610 Clear filters enhancement, port it onto the then-current
qualified baseline using a **new** release number; do not deploy
the old 610 branch over this fix.
