# Release 724 — One mobile Gym machine navigation

**Verified installed DEV baseline:** Release 723 `764efd20f0fe6ac643d7940eb8178387a530f842`.

## What changed

Rapid Gym previously showed Previous / Next Machine controls twice: once
adjacent to Save Set and again after the Rest Timer. Keep the first, more useful
version and remove the latter. This shortens a phone workout without losing
any destination. Also remove three dead CSS rules from the old navigation and
the unused legacy `ux673-gym-links` group, retaining current direct
links, touch targets, offline draft controls, and header navigation.

The change has no Python router, database, logging, CSRF, authorization,
or rest timer logic changes. Original Release 723 visual-regression proofs
now compare its immutable source commit, rather than assuming historical
CSS is perpetually identical to the latest source.

## Change-scoped verification

Jinja structural checks, one navigation and original signed POST forms,
original 723 stylesheet proof, legacy rapid-gym server tests, 320/390/430
signed Chromium workout flows with real in-session machine addition, the
completed/accidental delete fixtures, and Overview CSS unchanged.

Run only in guarded isolated DEV qualification, install the exact passing
commit to DEV after receipt verification, and never promote PROD without
a separately explicit instruction.
