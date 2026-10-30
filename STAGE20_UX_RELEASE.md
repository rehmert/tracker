# Stage 20 — Test database isolation and concurrent dose requests

Test-only release. `tests/conftest.py` now sets `TRACKER_DATA_DIR` to a new process-local temporary directory before application imports, even if an existing environment variable points to a live database. It also fails closed if app configuration was already imported against a different data directory.

`tests/test_stage20_concurrency_isolation.py` verifies isolation, two simultaneous 8 mg requests against a 10 mg vial, and two simultaneous requests with the same durable submission token. Both races must result in exactly one dose and correct remaining inventory.

Run `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_stage20_concurrency_isolation.py tests/test_stage19_atomicity.py tests/test_stage18_dose_mutations.py tests/test_stage17_dose_blend_integrity.py`.

Tests still cannot simulate power loss, hardware faults, or large-scale contention. No production code or schema changes.
