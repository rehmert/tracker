"""Regression checks for consistent vial update safeguards."""
import math
from pathlib import Path


def test_vial_routes_reject_nonfinite_content_and_volume():
    source = (Path(__file__).parents[1] / "app/routers/vials.py").read_text()
    assert "not math.isfinite(content_value)" in source
    assert "not math.isfinite(vol)" in source

def test_single_and_bulk_vial_updates_protect_dosed_sealed_status():
    source = (Path(__file__).parents[1] / "app/routers/vials.py").read_text()
    assert 'status == "sealed" and v.doses' in source
    assert 'proposed["status"] == "sealed" and vial.doses' in source
