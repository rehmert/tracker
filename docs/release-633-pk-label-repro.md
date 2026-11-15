# Release 633 — PK quick navigation, NIIMBOT media guide and dependency replay

## PK Simulator

The current page already supports protocol, what-if, scenario and multi-schedule workflows. Release 633 adds a compact jump bar above the workflow tabs for **Choose a protocol**, **Build a what-if schedule**, and **View the graph**.

- Buttons reuse the existing workflow tab clicks and scroll to existing anchors.
- No PK model, numerical assumption, saved scenario, API endpoint or dose log changes.
- No persistent browser state. Graph displays remain approximate, explanatory exposure estimates.

## NIIMBOT labels

The single-vial and multi-vial label pages now display the physical **sticker** dimensions separately from the **whole strip** dimensions at 203 DPI:

| Layout | Sticker | Strip | Output pixels |
|---|---|---|---|
| 40x20 | 40 × 20 mm | 40 × 20 mm | 320 × 160 |
| 30x15x2 | 30 × 15 mm | 30 × 30 mm | 240 × 240 |
| 10x20x4 | 10 × 20 mm | 40 × 20 mm | 320 × 160 |

The print checklist emphasizes actual size / 100%, zero margins, full-strip media setup, feed orientation and a physical test strip. The guide responds to an unsaved layout selection but does not automatically print or change exports. Browser drivers differ: direct printing remains unverified; PNG/SVG exports are available for suitable local label software.

## Reproducible Python dependencies

The existing DEV-only `scripts/tracker_freshenv570.py` remains dry-run by default. A new `--execute --packages-only` mode downloads the observed pinned wheel set into a private disposable sandbox, generates SHA-256 wheel receipts, installs packages offline into a fresh Python 3.13 venv, and compares versions with the recorded baseline. It exits **before** downloading Chromium or executing either full backend/browser test suite.

Example, **after** deploying Release 633 to DEV:

```bash
cd /opt/tracker
sudo /opt/tracker/.venv/bin/python scripts/tracker_freshenv570.py --execute --packages-only
```

This validates Python package replay on DEV but is not a complete guarantee of clean-host reproducibility, OS/library compatibility, or hardware printer support.

## Verification

Run only focused tests for these features:

```bash
/opt/tracker/.venv/bin/python -m pytest -q --tb=short \
  tests/test_release633_pk_label_repro.py \
  tests/test_release570_freshenv.py \
  tests/test_release628_pk_simplified.py \
  tests/test_vial_label_sheets447.py
```

No CSRF modifications, database migrations, or deployment changes.
