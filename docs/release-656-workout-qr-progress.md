# Release 656 — Workout camera QR scanning and equipment progress

DEV baseline: b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25 (qualified Release 655)

Source branch: release/656-workout-qr-progress

GitHub is only a source-code repository. There are no GitHub Actions or PRs.

## Features

- The existing Workout page adds a **Scan QR with Camera** button when the
  browser offers a secure camera context and native BarcodeDetector for QR.
  Permission is requested only when the user taps the button.
- The scanner selects a rear-facing camera when available and decodes the code
  locally in the browser. It sends its decoded text only to Tracker's existing,
  authenticated /workouts/qr/scan lookup; **no external QR destination is opened**.
  Unknown scanned codes redirect to the local Add Equipment screen with
  the code prefilled for mapping. Manual QR text/URL entry remains available
  in all browsers.
- Stop, page navigation and background-tab events release the camera stream.
  Unsupported/denied camera access falls back to manual QR entry.
- Each machine has a **View Machine Progress & History** link. The read-only
  page shows total recorded sets, most recent set, heaviest recorded weight,
  and the latest 30 actual sets.
- An SVG chart and session table display heaviest recorded load for each of
  the last 16 sessions with logged sets on that machine. The chart displays
  recorded loads only: no guessed or extrapolated strength metrics.

## Data, security and compatibility

- Existing Release 654/655 workout SQLite tables, models, sets and routines
  are unchanged. No schema migration, backfill or database writes.
- Reporting is scoped with get_scoped_db390; no new anonymous endpoints.
- QR lookup remains exact-match. Decoded values must be at most 1024
  characters. The scanner never fetches/opens external QR URLs.
- The camera feature requires HTTPS (or an appropriate secure context),
  camera permission and BarcodeDetector support. Unsupported browsers still
  provide full manual lookup.
- Earlier releases' DEV missing-upload-tolerant policy stays in the existing
  deployment runner; PROD upload integrity remains strict.

## DEV-only qualification and deployment

1. Verify installed DEV is exactly Release 655, clean main, correct DEV
   identity and active service, and verify the pinned branch SHA.
2. In an isolated candidate worktree, run scripts/tracker-release-scoped656.sh
   with configured Python.
3. Run Python/Jinja/Bash/Node syntax checks, mocked camera behavior tests,
   focused historical Workout regression tests, deployment safety checks and
   the exact-SHA source review. Full suite is not requested.
4. Since no schema is modified, do not request a migration or alter the
   existing backup policy. Preserve the standard source recovery snapshot,
   fast-forward only after qualification, restart and runtime smoke.
5. Keep PROD untouched pending explicit approval and separate promotion.

The DEV launcher is scripts/tracker-workout-dev656.sh, downloaded via a pinned
GitHub source SHA and verified with Git's blob checksum before execution.
