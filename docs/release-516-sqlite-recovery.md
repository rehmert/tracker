# Release 516 — grouped SQLite and backup reliability

Base: Release 515 source candidate `2fcdf58a8aea2ec560c6665de626365bb7cbcffc`.
This release depends on Release 515 passing DEV; never promote 516 independently of
its verified base.

## Fixes
- Close SQLite connections deterministically in the administrator session
  authentication store, secondary read-only request handler, backup snapshot,
  backup reference audit, recovery audit, secondary backup generation,
  secondary isolated restore rehearsal, and maintenance inspection routes.
  Transactional session operations retain SQLite's commit/rollback context.
  Failed session connection initialization also closes its file handle.
- Validate ZIP entry uniqueness, member count, manifest shape and declared
  member sizes before decompressing archive members. Bound total uncompressed
  ZIP size to 64 GiB and files to 50,000 (far above normal Tracker storage).
  Reject malformed/truncated/malicious archive metadata.
- Preserve on-disk ZIP structure, manifest v1, app database schema, and all
  existing recovery APIs.

Tests: `tests/test_release516_backup_sqlite.py` validates normal backup creation,
a normal archive, duplicate ZIP names, mismatched file sizes, uncompressed
size/file-count ceilings, sqlite connection setup-failure closure, session
auth connection lifetime and secondary read-only connection lifetime.
All test DBs/backups are synthetic and disposable.

## Release gate
GitHub **repository only**: no Actions/cloud tests. After Release 515 DEV
success, deploy this exact commit to DEV using its guarded pinned release
script. Require full isolated browser acceptance, complete backend pytest,
verified source/DB/upload recovery archive and restore, DEV runtime smoke
and `EXIT_STATUS=0` before promoting this branch to main and PROD.
