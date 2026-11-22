# Release 749 — portrait mobile sidebar

Base: verified DEV Release 748 (bd59b6e84ded0e55f91c5d88908ef2a1372ea429).
No migrations, API, authentication, records, or PROD changes.

Cause: the mobile left rail has fixed height 100dvh while the inner
nav-scroll element is constrained to 55vh. Collapsed categories leave
a large unused white band beneath the visible navigation, especially
in portrait orientation.

Change: a last-loaded, phone-only CSS override sizes the drawer to its
visible content, capped at 100dvh; expanded menus scroll within the
drawer without a 55vh restriction. All links, ordering, favorites,
accessibility labels, theme choices, topbar, mobile dock and desktop
sidebar remain unchanged.

Qualification: 320/390/430/760px portrait, 640px landscape, 1024px desktop,
light/dark browser regression using actual shared CSS order, navigation
keyboard focus, overflow checks and shell/density unit tests. Focused only.
Use existing exact-SHA DEV-only agent and immutable receipts. PROD requires
separate user authorization.
