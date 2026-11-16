"""Release 639: both DEV and older PROD schema baselines are reviewed."""
from pathlib import Path

import pytest

from scripts import tracker_schema_review639 as schema

ROOT = Path(__file__).resolve().parents[1]
# Immutable, DEV-qualified Release 640 schema-review endpoint. Later food-only
# releases must not be added to the older 639 schema exception allowlist.
SCHEMA_REVIEW_TARGET = "e3efff1cc2dadd744744a3e40c2f2c199c76ff4f"



def test_dev_638_to_639_adds_only_product_facts():
    schema.review(ROOT, schema.DEV_638_BASE, SCHEMA_REVIEW_TARGET)


def test_prod_historical_baseline_verifies_both_regimen_schema_stages():
    schema.review(ROOT, schema.PROD_635_BASE, SCHEMA_REVIEW_TARGET)


def test_unknown_or_unrelated_model_baseline_does_not_gain_approval():
    with pytest.raises(ValueError):
        schema.review(ROOT, "HEAD", "HEAD")


def test_historical_branch_ref_is_immutable_and_ancestor_of_release():
    assert schema.git(ROOT, "rev-parse", schema.DEV_638_BASE).strip() == schema.DEV_638_BASE
    assert schema.git(ROOT, "rev-parse", schema.PROD_635_BASE).strip() == schema.PROD_635_BASE
    assert schema.git(ROOT, "rev-parse", SCHEMA_REVIEW_TARGET).strip() == SCHEMA_REVIEW_TARGET
    schema.git(ROOT, "merge-base", "--is-ancestor", SCHEMA_REVIEW_TARGET, "HEAD")
