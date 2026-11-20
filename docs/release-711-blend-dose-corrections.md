# Release 711 — correction and deletion of prepared-blend withdrawals

## User experience

The same Dose Log Administration timeline now offers **Review entry** for
either an individual vial or a prepared Blend. Each prepared-blend detail page
and its detailed withdrawal history link to the same correction page.

The correction page preserves the physical Blend source (no moving a draw
between unrelated mixtures). It edits the recorded timestamp, amount and
compatible unit, administration vs discard, injection site, notes and
explicitly recorded disposable supplies. Mixed-compound Blends accept
volume-only amounts; one-compound Blends additionally accept compatible
mass or IU units. The form uses the existing read-only correction-preview
JavaScript and a mandatory confirmation checkbox for deletion.

## Transactional accounting

BlendDose is updated in place. Corrections calculate available volume by
excluding the previous withdrawal first, then validate the new volume
against the same prepared container. No new DoseLog rows are created and
source Vial stocks are never recharged or deducted: their original
preparation transfers remain intact. A finished (fully drawn) Blend can
reopen after correction or deletion; a completed draw can still be corrected.

Old SupplyUsage rows for the BlendDose are credited back, and replacement
supplies are deducted once, under the same reserved SQLite write transaction
as the BlendDose change and audit snapshot. Supply item availability and
counted-quantity rules are checked BEFORE changes. Deletion restores the
whole recorded withdrawal and its linked disposables. A second deletion
returns 404.

Immutable ChangeAudit records use entity type \`blend_dose\` and the
BlendDose ID, action \`edit\` or \`delete\`, and fully capture before/after
physical source, time, volume, entered amount/unit, kind, site, notes and
supply usage. Historical legacy withdrawals without entered amount/unit
show the original stored volume; their pre-correction NULLs are preserved
in the audit snapshot.

## Release scope

No database schema migration, dependency upgrade, new inventory model, or
global CSRF configuration change. Original individual-vial dose correction
routes and historical Blend draw compatibility POST remain available.
SQLite schema is unchanged.

Branch: \`release/711-blend-dose-corrections\`.
Base: \`5e78dfcdc8d9612266aa2aca26755957bad02561\` (installed Release 710).

The isolated \`scripts/tracker-qualify711.sh\` requires root/systemd on
\`tracker-dev\`, PrivateNetwork, clean installed Release 710, an exact pinned
SHA and explicit changed-file allowlist. It uses detached source and
disposable SQLite, checks JavaScript asset impact, runs focused backend tests
and a real strict-CSRF Chromium HTTP/HTTPS native edit/delete lifecycle.
The qualifier cannot install on either server and prints an explicit
installed-DEV-unchanged marker.

After successful isolated qualification, \`scripts/tracker-install711.sh\`
loads the exact pinned standard deployer from the GitHub code repository
and installs DEV through the existing guarded release workflow. That
workflow independently reruns the scoped API/browser gate, snapshots
application source, verifies runtime and preserves a qualification receipt.
The signed DEV-controlled PROD promotion runs the exact
\`scripts/tracker-release-scoped711.sh\` gate on PROD's disposable
candidate before installing. No full application regression suite is
requested. PROD promotion is separate and never implied by a QA pass.
