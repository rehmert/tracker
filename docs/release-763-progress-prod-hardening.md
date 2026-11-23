# Release 763: Progress Dashboard production hardening

DEV base: 35f6aa42aac648f3ed5af527620bd5f4b702b486 (verified Release 762 DEV).
PROD currently installed: 04fd141daa17fd2055f9177527296eb9165a59d2 (Release 761).

## Targeted fixes

- Convert current form values as tape, body-composition mass, height, and goal weight unit selectors change, with labels updated simultaneously. Backend canonical storage remains centimeters/kilograms.
- Pick the newest non-null body-fat estimate from all dated observations; show method and date even when a newer composition record omitted body-fat percentage.
- Require two distinct dated navel-waist observations for a period change, and show those dates. The same-day last reading is the authoritative daily value.
- Clarify that protein nutrient-field completeness does not establish all daily meals were logged.

## Production schema catch-up (required)

- Release 762 introduced exactly five additive tables and new Base registration. Release 763's protected PROD deployment from installed Release 761 **must** specify both `--reviewed-progress-762` and `--db-migration`.
- Signed runner detects `app/progress_models762.py`, requires the production-only reviewed flag, and invokes the read-only `tracker_schema_review763.py` before executing data-changing commands.
- Review verifies exact installed PROD 761 base, ancestry of DEV-qualified 762 schema, identical ORM table definitions and no changes to pre-existing ORM or migrations files.
- The existing guarded production `--db-migration` path verifies SQLite and attachment backup and isolated restoration *before* installing code or restarting services. It also preserves the signed DEV approval, exact SHA and rollback checks.
- DEV 763 is a code-only change from installed DEV 762; do not re-create the schema or re-run a production-style catch-up on DEV.

## Verification

Run changed Python/template shell/JS syntax, exact read-only PROD schema review in the isolated QA worktree, legacy 604 impact preflight, focused API and Chromium 360/390/430 phone tests and adjacent vitals/workout regressions. Full suite is not needed for this bounded change.

No PROD authorization is implied by the DEV qualification or installation of Release 763.
