# Release 737 — Native left-side Regimen disclosure markers

## Correction
Release 736 added a custom right-side chevron. The requested reference is
the native RIGHT-pointing triangle positioned LEFT of "Log a supplement or
medication independently". All three triggers (Log independently, Add
supplement or medication, Add schedule) now use the same native list-item
summary styling. The marker changes to downward when expanded.

Remove custom right-side ::after, native marker suppression, and flex
summary presentation. Retain 44px minimum touch height, accessible native
details semantics and Edit/Delete/Archive styles. No data, endpoint, shared
CSS, JavaScript, or schema changes.

## Scoped qualification
Exact SHA only, isolated worktree and disposable data. Jinja syntax;
Chromium 320/390/760/1024 and both light/dark modes, computed native
marker parity and toggle, keyboard use, overflow, alongside existing
Regimen Edit/Delete/MACD tests. Historical Release 736 test updated
because this intentional design correction supersedes its old right-chevron
assertion; the full device/theme coverage is retained. Bash syntax and
Release 604 impact gate. No full suite; PROD requires separate approval.
