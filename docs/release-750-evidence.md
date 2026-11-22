# Release 750: Issues #10 and #56 evidence gates

Baseline: Release 749 e80edbfa5ef5c7d41a953be36c60c4828b4a86d7.
Source-only acceptance tests and scripts; no runtime features, dependencies,
database migrations, account flags or PROD changes.

## #56
Run real signed POSTs and account switching between two independently
authenticated secondary pilot users on disposable private workspaces.
Replay an owner-2 signed form while logged in as owner-3, verify rejection,
and verify both private databases and audit trails. Reuse existing private
workflow, unified login and isolated SQLite tests.

Main routes remain administrator-only and secondary pilot is gated.
This is NOT full primary-app multiuser MACD parity.

## #10
Clone installed Playwright Chromium resources into a private /tmp folder.
Verify executable hash, deliberately damage ONLY the disposable copy,
restore it from a verified private backup, and launch the restored Chromium
to render synthetic HTML. Never download or overwrite installed browser/OS.
QA runs with PrivateNetwork=yes.

This genuinely tests disposable browser restore/relaunch, but NOT an actual
OS package rollback, independent OS library reconstruction or host snapshot
recovery. Do not certify or close #10 on this result alone.

No private logs, browser files, synthetic records or host paths in GitHub.
No full suite. Production stays at 749 absent separate promotion approval.
