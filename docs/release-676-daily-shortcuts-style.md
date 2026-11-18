# Release 676 — Daily Shortcuts Style Parity

Baseline: Release 675 installed commit
`2e8f65d7c61c522a5ab01f78cd3783e15559ece3`.

The Release 675 links were grouped and given generic borders, but they did
not reproduce the existing **Today / Daily Shortcuts** action tiles. Release
676 corrects the actual rendered appearance while preserving navigation.

## Implementation

- Add `tracker-shortcut-buttons676.css` **after** the global Release 673
  mobile stylesheet so it wins the cascade.
- Reuse the actual Daily Shortcuts tile design tokens and sizing:
  `--surface`, `--rule`, `--ink`, `--teal`, 3.2rem
  minimum height, .85rem radius, and 750 font weight.
- Present main links as 3-column desktop / 2-column phone tile grids.
  Use one column on narrow screens and preserve the compact routine version.
- Style both the native More disclosure and **its expanded destination links**
  as matching, separate touch-friendly tiles. Inline machine-history links
  also receive a matching button-like treatment.
- Primary navigation uses the same `--teal` and `--teal-ink` tokens as
  Daily Shortcuts.
- Navigation retains semantic anchors (`<a href>`), not a button wrapped
  around a link; actions that change data remain their existing form buttons.

## Qualification

`scripts/tracker-preview676.sh` creates an isolated worktree without
installing code. Focused unit and Chromium checks compare actual computed
styles against the Daily Shortcuts controls at 320/375/390/430/768 widths;
verify More menu interaction, minimum tap size, no horizontal overflow,
preserved destinations, and the existing Workout, Today and Purchases
regressions. Full application suite is intentionally not requested.

No database, backend, route, CSRF or API changes. Promotion remains gated
by an exact readiness marker created only after isolated preview passes.
