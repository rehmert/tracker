# Release 597 — Purchase and supply-inventory CSRF qualification

Base: Release 596 \`9c3cc162a27b26a393ed9740c93b9e0e8bea5f51\`.

This is a targeted signed Chromium lifecycle for six previously unqualified
unsafe routes: purchase creation/update; inventory supply-category creation,
supply addition, supply usage, and pill usage.

Both HTTP and HTTPS execute through the existing same-origin Chromium fetch
wrapper and its CSRF-signed request headers, with scoped original POST
response assertions. For each route an unsigned independent API-context
POST must return 403. Data checks are restricted to the guarded disposable
\`/tmp/tracker-browser-qa.*\` SQLite database and confirm purchases, shipping
cents, edited notes, categories, quantities, remaining stock, and one recorded
usage per consumed supply type.

The test uses unique random fixture names across independently scheduled
HTTP and HTTPS examples. In particular the category's random prefix precedes
the server's 20-character key truncation. The test uses regular database
transactions via the application's existing routes and does not import or
modify the installed production data. Existing four-worker browser
concurrency remains mandatory.

Source-only route counts under the unchanged 144-route inventory:
**83 source witnesses, 61 without source witnesses; 70 explicit
full-gate witness-manifest routes.** These counts do not certify runtime
qualification. Other purchase endpoints remain outside this batch. No
global strict-CSRF enablement, application behavior changes, schema changes,
account/session changes, or release-controller changes are included.

Qualify with the full guarded DEV browser and backend gates before any
promotion to PROD. Maintain the established dry-run, explicit approval,
and exact-commit production promotion process.
