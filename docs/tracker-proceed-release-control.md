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


## Fast server-triggered push notifications

The pinned installer now adds a separate Python notifier as a best-effort
ExecStartPost for the existing DEV release agent. Immediately after an agent
cycle completes, it checks the latest published sanitized receipt and sends
a short push alert through ntfy.sh when:

- DEV installation succeeds: Release N is ready for hands-on testing.
- Qualification, installation, or promotion fails or is blocked/unknown.
- A separately approved PROD deployment succeeds.

Successful intermediate qualification/preflight stages are silent. Repeated
agent cycles are deduplicated by immutable receipt ID. Failed notification
attempts retry on later agent cycles without rerunning deployment stages.
Notification delivery errors cannot change a deployment result.

The installer generates a random 192-bit topic, stored locally at
/etc/tracker-release-notify.json, readable only by root (0600). It prints
the subscription URL to the installer's terminal; never to GitHub. Subscribe
to it using the ntfy web app or mobile app and enable notifications. ntfy.sh
is an external provider: anyone knowing the topic can read these messages,
so keep the URL private. Messages include only the release number, action,
status and short code SHA; never logs, medical information or credentials.

To send a test push after subscribing:

    sudo /usr/local/sbin/tracker-release-notifier.py --test

Push alerts go to the subscribed phone/browser, NOT into this ChatGPT thread.
ChatGPT-native autonomous event handling would additionally require a
supported Work app-event task or a separately configured Workspace Agent
API trigger and token. Neither is provisioned by this notifier. Notification
latency is driven by the DEV agent and push provider, not the hourly ChatGPT
scheduled-task interval.


## Event-driven ChatGPT Work bridge (GitHub pull requests)

The DEV agent now installs another best-effort, root-owned post-run hook:
`/usr/local/sbin/tracker-release-pr-bridge.py`. After a release receipt
has been committed to the receipt branch, the hook verifies that the
immutable per-request JSON matches the latest receipt, then commits a
minimal public-safe event pointer to the dedicated branch
`tracker-release-events`. A single long-lived **draft PR**, titled
`[tracker-release-event] Tracker receipt trigger — DO NOT MERGE`,
targets `main` and remains unmerged. Each new event commit updates
the PR head and produces a GitHub PR **synchronize** event.

ChatGPT Work can use the configured GitHub PR opened/synchronize trigger
to respond to those events. Work MUST verify the immutable receipt ID
and its status directly on `tracker-release-receipts` before changing
any release command. The PR body or event marker alone never proves
qualification or installation and never authorizes PROD.

The bridge does not call ChatGPT directly or store a ChatGPT API key on
DEV. It sends only `request_id`, release number, action, status,
40-character SHA, and the relative receipt path. Other receipt content,
test failures, source file names, raw logs, credentials and medical data
never enter the event PR. The normal Git checkout, code branch,
release-control queue and application data are not altered by the hook.

The permanent PR must remain a draft and **MUST NEVER BE MERGED**.
A closed or deleted PR will prevent event delivery; the hook itself
cannot recreate or reopen a PR. Failed GitHub delivery is logged as a
bounded local error and retried next timer cycle (with the same receipt
ID); it cannot change the original release result.

For a root-owned diagnostic preflight on DEV:

    sudo /usr/local/sbin/tracker-release-pr-bridge.py --check

This validates both Git branches and the published receipt without
triggering a new PR synchronize event.
