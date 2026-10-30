# Stage 7 — Backup Verification UX

- Adds a per-archive **Verify now** button to the Backups page.
- Verification reads the archive and validates its manifest, every file SHA-256 checksum, and SQLite integrity.
- Reports success or failure on the Backups page; never restores or changes user data.
- Limits verification to named Tracker archives inside the configured backup directory.
- No schema migration.

Note: this does not verify off-server copies or perform a test restore. Run a separate recovery drill before relying on backups.
