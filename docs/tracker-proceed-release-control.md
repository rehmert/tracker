# Tracker release control: one “proceed” per stage

After one-time installation on tracker-dev, replying “proceed” means:
read the latest sanitized receipt, inspect the pinned release state, and
authorize only the next appropriate stage. It does not authorize the entire
pipeline to run uninterrupted.

## Three Git branches

* ops/tracker-release-control: versioned agent/installer/tests (code only).
* tracker-release-requests: ChatGPT writes control/current.json, one unique
  request for one release action at a time.
* tracker-release-receipts: DEV publishes receipts/latest.json and
  receipts/<request_id>.json with outcome, approved marker values, failing
  test *filenames* and test counts. Never merge these into app main.

The receipts branch is the narrow, explicitly approved exception to the
code-only GitHub convention. No raw log, medical information, SQLite data,
attachment, credential, or secret is published. Complete root-only logs
remain on DEV at /var/log/tracker-release-agent/<request_id>.log.

## Actions and dependencies

1. qualify: pinned DEV-only detached, PrivateNetwork qualification.
2. dev_install: requires a matching successful qualify receipt; runs the
   existing guarded release installer on DEV.
3. prod_preflight: requires a matching successful dev_install receipt; checks
   actual DEV/PROD installed commits and signed promotion prerequisites.
4. prod_deploy: requires a matching successful prod_preflight receipt; runs
   the existing signed, DEV-controlled PROD promotion and verification.

Each request includes exact release number, base SHA, candidate SHA, branch,
action, unique ID and previous request ID. All non-qualify actions require a
matching prior success, the same exact target/base/ref/release, clean installed
source, and unchanged GitHub release ref. No stage is silently skipped.

The agent never runs arbitrary shell commands from the command branch. It
extracts only the known, versioned Git scripts from the exact release commit
and verifies object identity. The stock signed promotion system remains
responsible for backups, qualification receipts, approval, production
checks and rollback.

No release stage is retried automatically after a possible live action.
A crash produces an unknown receipt and requires inspection. A receipt
publishing failure is retried independently without re-running that stage.
Failed/blocked/pending receipts never automatically advance the pipeline.

## One-time installation

The pinned installer from ops/tracker-release-control sets up a root-owned
Python agent under /usr/local/sbin and a systemd timer/service to poll
GitHub requests roughly every minute. It neither installs a new application
release nor changes PROD. This is a one-time command on tracker-dev; after
it succeeds, normal operation needs only the user reply “proceed”.

A control-agent update requires a newly pinned, explicitly rerun installer;
the agent cannot silently replace its own code.

## Inspect local agent status

    systemctl status tracker-release-agent.timer --no-pager
    systemctl status tracker-release-agent.service --no-pager
    journalctl -u tracker-release-agent.service -n 50 --no-pager

When a detailed failure cannot be diagnosed from the deliberately bounded
GitHub receipt, a narrow local log inspection may still be needed.
