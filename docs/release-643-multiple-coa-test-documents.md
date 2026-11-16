# Release 643 — Multiple independent laboratory documents under one COA

## Purpose

Some labs issue a separate analysis document for each test of the same compound or lot. A Tracker COA record now supports one original certificate **plus any number of separately attached test documents**, uploaded in batches of up to ten files. The COA's vial assignments, verification status, metadata and original attachment are preserved.

## Usage

Open **COAs → View / edit**. Under **Individual test documents**, optionally enter a shared test label (e.g. purity, endotoxin, identity) and select multiple PDFs or images. Each file is independently stored, displayed, downloadable through the authenticated and workspace-guarded existing `/coas/{cid}/file` endpoint, and individually removable. The existing "Replace document" field still replaces only the original document and does not affect additional test documents. Deleting the entire COA deletes all its files, after the database transaction commits.

Only actual PDF/PNG/JPEG/WEBP files are allowed, 15 MiB per file. Failed batch validation or commit cleans up newly uploaded files and does not add partial database records. The read endpoint binds an additional file to its exact COA ID to prevent cross-record retrieval.

## Schema, safety and backups

Only one new SQLAlchemy table, `coa_documents643`, is appended to `app/models.py`. Existing COA records and their file columns are not rewritten. The existing `Base.metadata.create_all` creates the new table once. The signed DEV/PROD runner requires the narrow `--reviewed-coa-643 --db-migration` exception, a verified database/uploads backup, and the separate Release 643 schema reviewer before installation.

`app.backup_references341` now requires every additional test attachment to exist in verified backups. Attachment integrity audits share the same required-reference inventory.

## Qualification

The focused tests include `tests/test_release643_coa_documents.py` (upload, cross-COA 404, cleanup, individual removal, parent deletion, backup references), `tests/test_release643_schema_review.py` (schema only, rejection of unrelated changes and migration authorization), plus older COA compatibility and attachment access tests. Guarded DEV and PROD release gates retain the full required suite and isolated browser qualification; no application-wide CSRF enablement is introduced and no new HTTP route is added.
