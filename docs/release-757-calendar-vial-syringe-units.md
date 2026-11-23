# Release 757 — Calendar vial-specific mg to U-100 syringe calculations

Release 756 (initial DEV SHA 84d6579253fc892a546476b31c87cbe3938549c4)
introduced volume inventory and every-N-days forecasts. Release 757
continues on that ancestry, preserving immutable Release 756 qualification
receipts. The current PROD base is Release 755 at
bb83f1a59de3defd5fe6d0bc83ad09ed4d0cfdac.

## Behavior

- Store target dose in the existing protocol as mg, mcg or g.
- In each pending Calendar day entry and review-list row, allow the user
  to explicitly select a specific eligible vial. No silent selection.
- Calculate mg/mL from the vial's recorded effective content and the
  recorded liquid volume, using existing canonical vial_views math.
- Calculate withdrawal mL = planned mg / recorded mg/mL and U-100 syringe
  markings = mL * 100. Show target mass and vial concentration.
- Do not use IU as syringe markings; never assume 1 IU equals 1 unit.
- If volume, concentration, compatibility, expiry/BUD eligibility or
  recorded remaining mass prevents conversion, show the missing-data
  condition; do not derive from another vial or fabricate an amount.
- The explicitly selected vial moves via read-only GET to /doses,
  preserving the original mass target and scheduled time. Existing
  /doses/preview recomputes against the selected vial, including
  remaining inventory. Only signed Dose Log submission records a dose.
- For legacy mL plans, mixed-strength vials show physical liquid volume
  and volume-only supply duration, still labeled as mixed strengths.
  Physical liquid volumes never imply equivalent mg dose per draw.
- No schema migration, data rewrite, medication change, auto-administer,
  or automatic dose recording.

This is arithmetic on user-entered data, not a prescription recommendation.
Verify the vial label, recorded concentration and syringe scale and increments.

## Qualification

DEV first: use scripts/tracker-release-scoped757.sh with synthetic tests.
Require new Release 757 receipt and separate authorization for PROD.
Never overwrite an existing Release 756 qualification receipt.
