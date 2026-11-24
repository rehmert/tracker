# Release 767 — strict production schema review and backup for Release 766

Release 766 introduced one **new** workspace model module
`app/device_models766.py` and the separately guarded Food recipe metadata table.
Its DEV backup was verified and its 85 scoped tests passed, but the older
production runner recognizes schema changes only in a fixed path allowlist.
Without this release the newly registered device table would be created on
PROD startup without the mandated pre-migration SQLite/upload backup.

Release 767 does **not** alter app data models, routes, UI, or historical logs.
It is a PROD promotion safeguard to ship qualified 766 together with 767 in
one signed DEV-to-PROD catch-up from installed PROD Release 765.

- Exact installed PROD base: `8c67580611fd945d9ae83f8015f071a24ab6fee5`.
- Approved and DEV-installed Release 766: `45263b9659232b6ac6a922da38599f92842a32d8`.
- Sign and review the Release 767 target Git blob; fail if any 766 app source
  has been modified, any other schema/model file changed, or a device table
  already exists before the PROD migration.
- The signed `scripts/tracker_prod_remote568.sh` extracts this exact pinned
  pre-install guard and runs it **before** calling the existing release runner.
- PROD guard checks attachment hashes, verifies live SQLite integrity,
  creates private consistent SQLite+all-uploads archive with existing
  `app.backup.create_backup`, and independently verifies isolated restoration.
- Retain only the 10 newest Release 767 pre-install snapshots. No backup,
  medical record, raw log or credential enters GitHub.
- The existing release runner still performs its normal source snapshot,
  isolated qualifying tests, rollback controls, fast-forward and runtime smoke.
  This dedicated pre-install archive compensates specifically for its missing
  `device_models766.py` schema matcher without bypassing code approval.
- PROD requires the user's explicit approval (received in this conversation)
  and separate immutable `prod_preflight` and `prod_deploy` receipts.

No change to the existing DEV workspace table/data; 767 DEV installation
is tooling only. Its new qualified commit is the **combined** PROD target.
