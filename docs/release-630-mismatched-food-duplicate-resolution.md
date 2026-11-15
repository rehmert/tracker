# Release 630 — Mismatched Saved Food Duplicate Resolution

Release 629 displays matching-name/barcode groups and only permits merges when all stored fields are equivalent. Release 630 adds constrained resolution of mismatched versions without rewriting historical meal totals.

## User actions

- **Remove unused version**: Only a version with zero recorded meal entries can be deleted. The user explicitly chooses the retained product. Favorite status and meal-template references move to the keeper in one transaction. This changes nutrition of *future* meals created from affected templates, so the confirmation makes that explicit.
- **Keep separate and mark reviewed**: Record a fingerprint of the complete current group (IDs, names, serving descriptions, barcodes, and raw nutrients) without editing any food row, meal, or template. Acknowledged groups disappear from the unresolved view. An optional show-reviewed link displays them again. Any later change to the group invalidates its acknowledgement and returns it to the unresolved list.
- **Equivalent consolidation** remains unchanged and continues to transfer references in one transaction.

## Safety boundaries

- A mismatched saved version referenced by any historical meal **cannot** be deleted or repointed through this operation; the server checks this inside the removal transaction.
- The retained and removed IDs must be positive, distinct, existing records and directly connected by normalized name or a shared nonempty barcode.
- Existing storage authorization and CSRF middleware remain in place.
- No automated batch merge, inferred zeroes, database rewrite of historical entries, or silent reinterpretation of nutrition.
- Marking reviewed is not deletion; the review marker is a separate SQLite table created at first use of the duplicate review route.
- This is an administrator Food Journal workflow; other user workspaces are unchanged.

## Qualification

Targeted regression tests are added to `tests/test_release629_food_duplicates.py` for successful unused resolution, refusal when an entry exists, preservation of past totals, invalid pairs, review acknowledgement invalidation, route behavior, and the new UI form controls.

Release 630 is a fifth-release milestone: the **existing mandatory full browser and backend qualification** is required on DEV. Do not bypass the release tool's exact-commit evidence or rollback guards.
