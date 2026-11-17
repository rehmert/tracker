# Release 669 — Edit Existing Saved Foods

Branch: `release/669-edit-saved-foods`
Baseline: Release 668 (`c5ca4e1e226408b6d5784794dab5f73205b95c36`)

## Behavior

- Edit a saved food through Favorites, Recent Foods, Saved Food Search or a Recorded Meal.
- The editor loads the selected saved food by stable product ID, displaying its
  original name, optional barcode, serving basis and all 16 nutrients.
- Empty nutrient fields mean **unknown** and explicit zero means **zero**. All
  submitted values are finite, nonnegative and at most 100,000 in each field's
  units. No arbitrary or partial nutrient payload is permitted.
- Updates use the existing authorized Food Journal engine and a single SQL
  transaction, with SHA-256 comparison against the food as displayed when
  editing started to reject stale browser tabs.
- A change to a saved food also recalculates historical journal nutrition on
  every day that previously logged that same saved food. The edit form clearly
  warns and requires explicit confirmation if any existing meal logs use it.
- Existing meal dates, quantities, favorite links, and meal-template links
  stay attached to the same product. Source attribution is preserved.
- There is **no** schema migration, new database table, new auth path,
  background job or automatic update of unrelated saved-food versions.

## Qualification

Focused isolated tests for edit consistency, stale-write protection, invalid
inputs, historical totals and saved food navigation, plus selected legacy food
tests. The standard runner may require full QA if sensitive shared-core sources
are changed; this release does not request that exception.

The code-only readiness file must not exist until the isolated DEV preview
and exact-source review pass. Its complete content must be exactly:

`RELEASE_669_IMPLEMENTATION_REVIEWED=YES`

### DEV isolated preview (no install or PROD deployment)

```bash
sudo bash -c '
  set -Eeuo pipefail
  cd /opt/tracker
  git -c safe.directory=/opt/tracker fetch origin \
    refs/heads/release/669-edit-saved-foods:refs/remotes/origin/release/669-edit-saved-foods
  git -c safe.directory=/opt/tracker show \
    refs/remotes/origin/release/669-edit-saved-foods:scripts/tracker-preview669.sh \
    | bash -s
'
```

### DEV-controlled promotion (only after reviewed readiness and qualification)

The DEV launcher `scripts/tracker-release669.sh all` first deploys an
exact-commit DEV build, saves its guarded qualification receipt, and then
uses the existing signed DEV-controlled promotion pathway. PROD repeats the
Release 669 focused tests in its isolated target worktree. A code-only release
uses the existing no-migration backup skip marker.

No GitHub Actions or cloud-hosted tests/deployments are required.
