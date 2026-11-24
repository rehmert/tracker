# Release 775 — discoverable Google Tasks navigation

Release 774, already installed on DEV, introduced atomic Save all titles for
Google Tasks. Release 775 adds discoverable navigation and is intended to promote
to PROD **together with Release 774**, after user review.

- A dedicated **Google Tasks** destination appears directly after
  **Supplements & Medications** in the **Health & Progress** sidebar group.
  It uses the existing navigation link system, so it participates in
  search, favorites, page highlighting, reordering and mobile sidebar access.
- The icons map explicitly recognizes the Google Tasks destination; its
  JS cache version increments so updated icons load.
- **Protocols** includes a clear **Google Tasks settings** action alongside
  its existing workflow shortcuts, rather than as an easy-to-miss paragraph.
- **Supplements & Medications** shows the same action in its quick-action
  toolbar, without an unstyled text link.

No API, database, schema, Google task identity or sync changes. The existing
Google OAuth PROD-only guard remains unchanged. Qualification uses isolated,
change-scoped navigation and Google Tasks tests, with guarded DEV installation
first. PROD requires the user's later explicit approval; promotion from 773
to 775 will include the already-qualified 774 batch-title improvements.

See `docs/ux-batch-editing-guideline.md` for the future batch-save design rule.
