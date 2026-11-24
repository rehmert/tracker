# Release 776 — Google Tasks visible under default everyday navigation

Release 775 added a dedicated Google Tasks sidebar entry and clear
workflow shortcuts. This small follow-on ensures that Tracker's default
**Show everyday pages only** mode does not hide the new entry.

- Add `/integrations/google-tasks` to the existing essential-route set
  alongside `/regimen`.
- Bump the focus script's URL version to invalidate the browser cache.
- Preserve all existing focus preferences, custom hidden-link settings,
  navigation ordering, favorites, and active-page behavior.
- Keep Google Tasks under **Health & Progress** after
  **Supplements & Medications**, visible via the usual mobile sidebar.

No database, route, Google API, OAuth, or settings behavior changes.
Changed-scope DEV verification precedes deployment. The planned PROD
promotion from 773 to 776 includes DEV-qualified Releases 774, 775, 776
under a single guarded deployment once separately authorized.
