# Release 709 — All ten remaining post-627 food and COA positive CSRF writes

Deployed DEV/PROD baseline remains Release 705,
`4c084ade9063b3b01c2de0a4a055d2e23470b2a3`.
Prerequisites are the recorded detached DEV-only 707 acceptance pass
(29 signed positive routes) and 708 acceptance pass (19 signed positive
Workout routes), each with a zero systemd exit status.

## Scope

This is a **source/test-only** branch on top of 708
`2b4b3f2053f2f7f3c90542afa597e8625921b430`.
No application router code, installed requirements, schema, production
database, service configuration or global CSRF setting is changed.

Ten newly authored Chromium positive-route witnesses close the final
post-627 additions that neither 707 nor 708 exercised:

- POST /food/duplicates/merge
- POST /food/duplicates/resolve-unused
- POST /food/duplicates/keep-distinct
- POST /food/saved/{product_id}/edit
- POST /coas/{cid}/attachments
- POST /coas/{cid}/attachments/{aid}/delete
- POST /coas/{cid}/attachments/{aid}/test-type
- POST /coas/{cid}/default-file
- POST /coas/{cid}/attachments/test-types
- POST /coas/{cid}/attachments/identifiers

Each route receives a missing-token request and a forged-token request
with the same valid business payload: both must be 403 and preserve the
relevant SQLite state. The browser then submits the valid cookie-matched
token; the server must report valid and perform the expected business
operation, including uploads, status changes or saved nutrients.
The suite uses local private `/tmp/tracker-browser-qa.XXXXXXXX/data`
SQLite and synthetic PDF bytes. HTTP and HTTPS schemes are both tested.

The food fixture seeds equivalent and non-equivalent products, checks a
merge actually removes the redundant row, resolves unused alternatives,
persists an exact-source distinct-review fingerprint, and saves a
version-checked edit with all sixteen nutrient fields. The COA fixture
creates an empty-document metadata COA, uploads an attachment, selects
it as default, edits its type individually and in bulk, saves per-file
task/verification identifiers, then deletes the document and checks the
default preference was removed.

The exact ten route declarations are pinned against the conservative
627/705 source ledger in `tests/test_release709_csrf_food_coa.py`.
They are registered exactly once in full strict Chromium QA and exposed
through narrowly targeted `--targeted-strict csrf-positive709`.
The targeted run is excluded from the one-full-suite duplicate count.

`scripts/tracker-csrf-positive709.sh` requires root systemd with a
separate private network namespace, a clean installed Release 705 DEV
source, a fetched immutable release branch SHA, and the cumulative
707–709 file-change allowlist. It compiles no new deployment code,
performs scoped source and route-catalog qualification and then the
real signed HTTP/HTTPS workflows. It cleans up detached worktrees and
browser synthetic data, leaves DEV/PROD unchanged and **never enables**
global strict CSRF.

If runtime-qualified, the new acceptance totals become 29 + 19 + 10 =
**58 newly proven signed positive-route witnesses**. This is NOT a
completed Issue #9 closeout. The original 92-route source-only ledger
remains unchanged until a separate signed-runtime receipt reconciling
every route and all manual/session reviews is completed. The remaining
**34 old historical positive-route gaps**, 155 manual reviews, six
independent session/account routes and full strict browser release
qualification are still open.


## Retry correction: parallel duplicate grouping and real form fingerprint

The first Release 709 targeted Chromium run qualified 3/4 parameterized
browser cases and failed the HTTPS food case while looking for a test-
calculated fingerprint in the duplicate review form. Source analysis
showed that `near_name_key641` uses the **first two normalized words**
of a saved food name for grouping. The original test used the common
first two words `QA709 distinct` in BOTH HTTP and HTTPS xdist workers,
so independent scenarios could be combined in one group and the hand-
calculated two-row fingerprint would not match the rendered multi-row
group. No application security or CSRF logic was changed.

Every test seed name now uses a unique first-word token, plus a
distinct action name as the second word, so parallel workers cannot
combine their groups. The review test locates the actual matching
`section.food629-group`, asserts the exact two expected version IDs
are rendered, and reads the SHA-256 fingerprint directly from that
group's hidden native form field. The valid request must still persist
the acknowledgement; tokenless and forged attempts must still deny
without mutation. Source regression tests cover the old first-two-word
collision and new unique namespacing. The full and targeted browser
runner wiring and deployed app remain unchanged.
