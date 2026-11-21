# Release 731 — Doctor-ordered fractional tablet doses

**DEV base:** Release 730 `13ed014d24ba5658a69ccb15b6d8e1a247c7575c` (verified installed).

Track a whole manufactured tablet strength separately from the prescribed
milligram dose, planned tablet fraction and actual tablets taken. For
example, 20 mg per whole tablet × 0.5 tablets = 10 mg administered.

## Scope

- New additive `regimen_tablet_schedule731` and `regimen_tablet_entry731`
  tables; no ALTER on earlier regimen schedules/entries and no backfill.
- Schedule: choose manual amount or structured tablets; enter strength
  mg/tablet, the explicitly ordered mg, and planned tablet count.
  Server rejects mismatch between prescribed mg and calculated plan.
- Actual intake: select tablets really taken (including quarter/half).
  The server calculates and saves actual mg, actual tablet count,
  prescribed mg and original strength, separately from each schedule.
- A later prescription/schedule edit does not rewrite historical intake.
  History correction updates the audited entry and snapshot.
- Skipped records never consume tablets. Legacy/manual entries remain.
- Browser previews are advisory; server recomputes and validates all values
  using Decimal with no client-trusted calculated dosage.
- Current regimen lacks a linked pill stock ledger, so there is **no
  automatic inventory deduction**. A fractional tablet count is preserved
  for later integration. No food totals, vials or injectable logs change.
- Tablet splitting is not automatically recommended; only use tablets
  confirmed suitable for splitting by the prescribing professional.

## Qualification

Guarded, pinned isolated worktree and disposable SQLite, PrivateNetwork=yes
worker, source change allowlist, impact preflight, Jinja/form structural
tests, schedule/create/edit/intake/correction/skip validation and auditing,
and Chromium form controls at phone widths. Additive shared model gets
focused schema / regimen compatibility tests, not a full app suite.

## Additive schema promotion gate

The existing guarded deployer requires **both** a reviewed schema flag and
verified migration backup when `app/models.py` changes. The first DEV
installation correctly failed closed with `StageCommandError`: its installer
omitted `--db-migration` / `--reviewed-tablet-731`. No rerun of that failed
request is allowed. The corrected candidate adds a **release-specific**
AST-based schema review, restricted to the two additive tablet tables and
an unchanged existing ORM schema, and a dedicated reviewed flag in the
versioned runner. The installer now passes both flags so the standard
backup, isolated restore verification, schema review and post-install
runtime qualification all execute before success. The schema gate is
checked independently during new qualification.

A fresh exact SHA, separate qualification receipt and separate guarded DEV
installation request are required. PROD promotion must use the same native
signed schema/backup gates and is not authorized by this change.

DEV installation only after exact qualification passed. No PROD
preflight, authorization or deployment without user's explicit instruction.
PROD remains at Release 727 unless separately promoted, and promoting
731 eventually includes 729 Labs mobile + 730 medication/catalog updates.
