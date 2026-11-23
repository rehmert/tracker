# Release 760 — guarded PROD 755-to-760 schema catch-up

DEV base: installed Release 759 eb1d3ab3c66aa8d2c8af8cc7ae4ed85bf4d2357d.
Expected PROD base: Release 755 bb83f1a59de3defd5fe6d0bc83ad09ed4d0cfdac.

This tooling-only release carries all tested Release 759 application
changes unchanged. PROD has not yet installed the nullable production date
field introduced in Release 758. The signed, streamed PROD installer now
pins the exact Release 755 base and passes both --reviewed-vial-758 and
--db-migration for this one approved 760 catch-up.

The target-pinned runner independently verifies exactly one additive
nullable field in the model and migrations files, verifies upload integrity,
backs up SQLite plus attachments, restores backup in isolation, performs
scoped source qualification and confirms runtime health. It refuses any
unreviewed schema difference. DEV already applied the schema in Release
758 and this release has no DB migration on DEV.

No user-facing application changes, dose/inventory rewrites, or data on
GitHub. PROD requires explicit authorization, read-only preflight, and
immutable stage receipts before deployment.
