# Release 804: visual refinement, mobile UX, personalization

Base: the exact Release 803 DEV/PROD SHA (3e51216bc720d0a87465d072771fefe9b1e15d3a).
Target: `release/804-visual-mobile-personalization`.

- Refine existing design-system surfaces, headings, numbers, nested cards, tables and keyboard focus without altering semantic colors, server-managed theme overrides or existing action primitives.
- Keep action groups horizontal where space permits; ensure 44px mobile targets, controlled horizontal scrolling, and a viewport-bounded, keyboard-accessible Preferences panel.
- Put less common sidebar customization controls in a native collapsible Advanced navigation group while keeping display density, appearance and everyday-page focus prominent.
- Show a live summary of saved display/theme/navigation choices. Continue to use the existing `tracker-density`, `tracker-theme` and `tracker.navigation.focus.v1` preference keys; do not migrate or reset stored choices.
- Preserve Today/Dashboard links, routes, forms, user data, dashboard layout, favorites, user theme CSS and all app endpoints. No schema, dependency, Google integration or service changes.

Acceptance: source/Jinja/JS syntax, scoped HTTP contract, 320/390/430/1024px Chromium checks in light/dark and compact/balanced, visible control and focus assertions. PROD is separately authorized.
