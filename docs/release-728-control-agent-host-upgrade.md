# Release 728: Corrected DEV release-controller installation

The versioned controller already implements the correct catch-up exception:
only `prod_preflight` may use the *installed PROD* base rather than the
base of the previous successful DEV installation. All other receipt fields,
stage order, and exact target are checked. The signed native preflight
independently verifies actual PROD base, ancestry, services, approval, and
GitHub main. The installed controller previously returned
`StageChainBlocked` for Release 726, consistent with an outdated host copy.

This version adds a regression reproducing that recorded release transition
and verifies the installed copies of agent, notifier and event bridge against
the reviewed source Git blobs.

Host install remains an explicit operator action from tracker-dev.
Extract `scripts/tracker-release-agent-install.sh` from pinned
`ops/tracker-release-control` to a root-only temporary file; verify its
Git hash, then invoke it with the exact pinned branch SHA. It refuses
installation while the worker is running, executes scoped offline tests,
and never changes PROD or the application checkout.

Success markers:
`TRACKER_RELEASE_AGENT_INSTALLED_OBJECTS=VERIFIED`,
`TRACKER_RELEASE_AGENT_INSTALL=SUCCESS`,
`TRACKER_RELEASE_AGENT_PINNED_COMMIT=<full ops commit SHA>`.

Do not replay the old blocked Release 726 preflight; it was subsequently
deployed through the signed operator path. Future PROD stages require
separate explicit approval.

Next priorities: mobile UX, measured performance, dependencies,
then strict CSRF qualification. No full regression suite is required
for this tooling-only change.
