# Release 710 — one physical-vial dose workflow for prepared blends

## User-facing behavior

A prepared Blend is one **physical destination vial**, even when it contains
several transfers from a single compound or one or more different compounds.
The standard Dose Log `/doses` picker now lists stocked Vials **and** active
prepared Blends. Prepared vials use an explicit `blend:<id>` selection key
so a Blend ID can never be mistaken for a purchased Vial ID.

The same form presents the amount and unit, date/time, administration vs
waste, injection site, explicit disposable supply use, notes, final review,
and a live calculation preview. The Blend detail page links to
`/doses?source=blend:<id>` with that physical source preselected.
The older Blend draw POST remains for historical compatibility but is
secondary to the canonical Dose Log.

For a blend containing **one compound**, even when assembled from multiple
source vials, Tracker sums its recorded transferred content and accepts a
compatible mass/IU amount or the actual drawn volume. For blends containing
**multiple compounds**, it only accepts a liquid-volume entry (mL/uL)
because a single mass/IU number would ambiguously represent more than one
ingredient. The preview shows volume, U-100 graduation arithmetic, remaining
blend volume, and every recorded constituent amount. Nothing constitutes a
dose recommendation.

A newly recorded mixed dose creates **one BlendDose**, with its actual
entered amount/unit, site, time, kind, notes, and linked disposable supply
usage. It NEVER creates phantom DoseLog rows for source Vials, whose stock
was already consumed during the physical blend preparation. Blend inventory
is deducted by one draw volume; the remaining physical container is marked
finished only when depleted. The unified administration timeline presents
the draw once and shows the original entered unit and site. The standard
one-use submission token, SQLite write reservation, stock checks, and
manual supply-selection checks all apply.

## Schema compatibility

`BlendDose` gains additive `site`, `entered_value`, and `entered_unit`
columns. `SupplyUsage` gains an optional `blend_dose_id` foreign key.
`migrate(engine)` idempotently adds these fields only when the tables
exist. Existing BlendDose rows retain NULL amount/unit fields and continue
to use the recorded volume. Existing SupplyUsage and DoseLog records are
unchanged. No destructive SQL or copying of source-dose rows.

## Scope and qualification

Based on installed DEV/PROD Release 705
`4c084ade9063b3b01c2de0a4a055d2e23470b2a3`, intentionally separate
from the still-unpromoted security-test 707–709 branch. The narrowly scoped
candidate touches dose page/router, additive models/migration/supply linkage,
the blend-detail navigation, source-context JavaScript, the existing
Release 564 compatibility test, the browser qualifier, and new positive
API/browser acceptance tests. No unrelated Tracker feature is modified.

`scripts/tracker-blend-vial710.sh` is stored in the GitHub code repository,
loaded by exact SHA, and executed through a `systemd-run --wait --pipe`
command on `tracker-dev`. This streams stdout directly to the current
SSH terminal while systemd owns the isolated job. It requires clean
installed Release 705, `PrivateNetwork=yes`, a pinned ancestry/changed-file
scope, a detached worktree, an ephemeral SQLite data directory, focused
backend regressions, and signed Chromium HTTP/HTTPS browser acceptance.
It removes temporary data and source worktree. **It never installs or
deploys Release 710.**

The DEV-only isolated source/API/browser qualification passed on
commit `31d426763d8bfeeee31fecd7063559a4480f5d9f`.
That candidate has NOT been installed. A follow-up installation-readiness
change introduces the explicit `--reviewed-blend-710 --db-migration`
gate in the standard deployer, a byte-exact source/schema reviewer,
a focused shared-dose regression plus signed HTTP/HTTPS Chromium gate,
and the same reviewed/backup flag in PROD's signed remote installer.
The new candidate must be qualified again; passing the earlier commit
does not approve new installer code.

The DEV installation path is `scripts/tracker-install710.sh <pinned-commit>`.
It invokes the existing standard release runner, which performs the
reviewed migration checks, focused isolated tests, verified SQLite and
present-attachment backup, isolated backup restore, fast-forward install,
bytecode refresh, runtime smoke, and rollback attempt on install failure.
A code-only rollback does not undo an additive SQLite schema migration.
PROD requires a separate exact-commit signed DEV promotion receipt and
a successful preflight with the actual installed PROD base.
Neither workflow enables global CSRF enforcement.

This is still a scoped release: no routine full application suite is
requested; shared-dose and adjacent Calendar/inventory tests are included.
No package downloads, GitHub-hosted backups, or uncontrolled PROD SSH
operations are part of the release.

## Release 613/668 compatibility regression

During the first DEV-only Release 710 qualification, the old Release 613
Calendar reconciliation test failed because it asserted positional ordering.
Release 668 intentionally sorts same-time events by compound name. Its
post-668 behavior is correct: Example (recorded), Extra (extra), Other
(recorded). The historical regression now verifies identity and blend
provenance by compound ID, and independently checks the documented sort.
The Calendar implementation was not changed. The fix is included in the
Release 710 exact-file qualification allowlist, so the next DEV run
executes it together with the rest of the targeted tests.

## Deliberate non-changes

Existing BlendDose rows are not rewritten into DoseLog. The legacy
`/blends/{id}/doses` POST stays available for older integrations, but
normal interactive logging uses the consolidated form. Existing
independent blend creation/transfers, Calendar matching, COA mapping,
vendor purchases, and Vial inventory records are unchanged. Editing or
deleting a historical blend draw is NOT claimed to have become the same as
ordinary DoseLog correction; that requires its own audit-safe follow-up.
