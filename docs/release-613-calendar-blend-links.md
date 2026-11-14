# Release 613 — Calendar links back to recorded source blends

Base: deployed and qualified Release 612,
`121b60587dafaa9d2d91ad7a0ff07e8b75857c02`.

Release 611 made actual blend doses visible in the Calendar, but users still
had to navigate manually to the blend to inspect recorded draw details.

## Changes

- The read-only calendar reconciliation retains the source `blend_id`
  from the actual record when a blend dose matches a projected occurrence.
- The month grid displays a **View source blend #ID** link for both
  protocol-matched and unmatched actual administrations from blends.
- Ordinary vial administrations never gain a blend link.
- No changes to inventory, dose storage, calendar matching criteria,
  protocol schedules, database schema, or authentication and CSRF.
- The original held Release 610 clear-filter work, promoted as
  Release 612, remains intact.

## Tests

The existing Release 611 integration test now verifies Calendar HTML links
to the recorded source for both matched and unmatched constituents.
A focused reconciliation test ensures the provenance of single-vial and
blend records stays distinct.

Guarded DEV qualification and human visual acceptance are required before
signed PROD promotion. Maintain 16 pytest workers with
`--dist=loadfile` and systemd `MemoryMax=16G`.
