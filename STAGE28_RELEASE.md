# Stage 28 — Pill inventory concurrency protection

- `/supplies/{sid}/dose` now obtains a SQLite `BEGIN IMMEDIATE` reservation before reading inventory.
- Adds durable submission-token replay checks for pill usage.
- Invalid requests roll back the transaction.
- Two new concurrent-request regression tests cover overdraw and identical-token replay.
- No schema migrations or automatic data modifications.
- Targeted test run: 5 passed (`tests/test_stage28_pill_concurrency.py` and `tests/test_stage20_concurrency_isolation.py`).
- Full test suite was attempted but exceeded the available execution timeout; its outcome is unverified.
