# Stage 21 — Concurrent blend and purchase tests

Test-only release. Adds `tests/test_stage21_concurrent_inventory.py` with simultaneous HTTP submissions for blend source depletion, identical blend creation, blend draw depletion, identical draw replay, and purchase header replay. Tests run against the temporary SQLite database established by `tests/conftest.py` in Stage 20. No production code or migration changes.

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_stage21_concurrent_inventory.py tests/test_stage20_concurrency_isolation.py tests/test_stage19_atomicity.py tests/test_stage18_dose_mutations.py tests/test_stage17_dose_blend_integrity.py`
