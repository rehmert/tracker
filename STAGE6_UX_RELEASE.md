# Stage 6 — Saved Vial Views and Search Accessibility

- Saved vial filter views (status and compound) using browser localStorage, with save, apply and delete controls. Up to 30 views. No database migration.
- Status filter links retain the selected compound; compound changes retain status.
- Global search input now declares combobox/listbox accessibility semantics and updates expanded/active descendant states.
- Views are browser-local, not shared across devices; no inventory or dosing data stored.
- Existing backend search and data mutation behavior unchanged.
