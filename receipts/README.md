# Tracker release execution receipts

A DEV-owned release agent publishes bounded, sanitized JSON receipts here after executing an approved request. Raw logs, personal data and backups remain on DEV. Never merge this branch into app `main` or release branches. `receipts/latest.json` and `receipts/<request_id>.json` are generated; neither is evidence of success unless status is `passed` and expected markers are present.
