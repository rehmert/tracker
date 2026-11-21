# Release 725 — Rest Timer at the end of the actual set-entry panel

Installed DEV base: Release 724 at `335d7abc65d1f9c23d41328dff91c27c32729834`.

The timer was previously after optional Load Setup, Offline/Draft Tools,
Edit/Add Machine, and Planned Training Groups. This release moves its
unchanged section directly after set-entry panel, before advanced options,
while keeping it visible for an active workout without a selected machine.
All REST timings, timer state JS and DOM IDs, native set-logging and
completion forms, machine-navigation links, and CSRF behavior remain intact.

Qualification is isolated and exact-SHA: focused backend/Jinja tests,
original timer JavaScript browser checks, authentic signed HTTP/HTTPS
Chromium active machine insertion and session deletion regression, and
no full suite. Never promote PROD without explicit separate authorization.
