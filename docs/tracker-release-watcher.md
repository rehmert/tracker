# GitHub-managed Tracker release watcher

- GitHub repository: `rehmert/tracker`
- Source branch: `ops/tracker-release-control`
- Executable: `scripts/tracker-release-watch.sh` (this is **not** the app's `scripts/tracker-release.sh` production deployment script)
- Offline regression tests: `tests/test_tracker_release_watch.py`
- Installed location on `tracker-dev`: `/root/tracker-release.sh`

The watcher reads the queued request from the release-request branch, validates
all metadata, and checks its immutable release receipt. Already-completed
requests are shown without a service restart. Pending DEV requests start the
existing guarded systemd agent; the watcher reads journal progress, switches to
the exact request log, and reports the signed stage outcome. Invalid queue
metadata, failed receipts and PROD commands fail closed.

## Reinstall/upgrade

Fetch `ops/tracker-release-control` on `tracker-dev`, stage the exact source and
its test in a temporary directory, compare Git object hashes, run `bash -n`
and the focused offline test, and only then replace `/root/tracker-release.sh`.
Do not overwrite the app's own deployment script. Commit new watcher changes
and passing tests before recommending an update.

The watcher executes no direct release code beyond starting the existing
`tracker-release-agent.service` for an already-approved DEV stage. It never
queues an authorization, installs code by itself, or promotes PROD.
