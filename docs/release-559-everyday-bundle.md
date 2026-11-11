# Release 559: Everyday workflow bundle

This release makes existing features easier to reach.

No new database tables, migrations, or application routes.

Changes:

- Dashboard: everyday shortcuts for Today, doses, vitals,
  food, water, calendar, progress and inventory needs.
- Mobile Today: food, water and review shortcuts.
- Quick Entry: searchable food, water and progress actions.
- Models: remove the consecutive duplicate COA relationship
  and property definitions without changing their behavior.
- Frontend: one scoped stylesheet.
- Tests: templates, routes, anchors and model regressions.

All shortcuts navigate to pre-existing routes.

No automatic dose, inventory or health-record writes.
No account or production data changes.
