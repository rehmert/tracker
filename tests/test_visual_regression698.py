"""Release 698: screenshot comparison mathematics and isolation contracts."""
from io import BytesIO
from pathlib import Path
import os

import pytest
from PIL import Image

from scripts.tracker_visual_regression698 import (
    ANCHORS, MAX_CHANGED, PAGES, THEMES, VIEWPORTS, difference_png,
    require_loopback, save_failure,
)

ROOT = Path(__file__).resolve().parents[1]


def png(color, size=(64, 48)):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def test_698_compare_identical_image_is_exact():
    a = png((245, 245, 245))
    diff = difference_png(a, a)
    assert diff.changed == 0
    assert diff.fraction == 0
    assert (diff.width, diff.height) == (64, 48)


def test_698_detects_meaningful_visual_change():
    a = png((250, 250, 250))
    b = png((20, 30, 45))
    diff = difference_png(a, b)
    assert diff.changed == diff.total == 64 * 48
    assert diff.fraction > MAX_CHANGED
    assert difference_png(a, png((247, 247, 247))).fraction == 0


def test_698_rejects_incompatible_screenshot_sizes():
    with pytest.raises(ValueError, match="dimensions"):
        difference_png(png((255, 255, 255)), png((255, 255, 255), (65, 48)))


@pytest.mark.parametrize("origin", (
    "https://127.0.0.1:8000", "http://localhost:8000",
    "http://0.0.0.0:8000", "http://tracker-prod:8000",
    "http://127.0.0.1", "http://127.0.0.1:8000/login",
    "http://user:password@127.0.0.1:8000",
    "http://127.0.0.1:8000/?token=secret",
))
def test_698_rejects_any_nonisolated_origin(origin):
    with pytest.raises(ValueError):
        require_loopback(origin)


def test_698_accepts_only_ported_loopback():
    assert require_loopback("http://127.0.0.1:49152/") == "http://127.0.0.1:49152"


def test_698_private_artifacts_only_on_difference(tmp_path):
    path = tmp_path / "review"
    save_failure(path, "today-phone-dark-top",
                 png((255, 255, 255)), png((0, 0, 0)))
    assert sorted(p.name for p in path.iterdir()) == [
        "today-phone-dark-top-baseline.png",
        "today-phone-dark-top-candidate.png",
        "today-phone-dark-top-diff.png",
    ]
    assert path.stat().st_mode & 0o077 == 0
    assert all(p.stat().st_mode & 0o077 == 0 for p in path.iterdir())
    with pytest.raises(ValueError, match="Invalid artifact"):
        save_failure(path, "../unsafe", b"", b"")


def test_698_real_page_coverage_and_no_production_capture():
    assert set(PAGES) >= {"overview", "today", "food", "doses", "vitals",
                           "gym", "vials", "purchases", "coas", "labs"}
    assert set(ANCHORS).issubset(PAGES)
    assert set(VIEWPORTS) == {"small-phone", "phone", "tablet", "desktop"}
    assert set(THEMES) == {"light", "dark"}
    script = (ROOT / "scripts/tracker_visual_regression698.py").read_text()
    assert "TRACKER_TEST_ISOLATED" in script
    assert 'parsed.hostname != "127.0.0.1"' in script
    assert "PIL" in script
    for prohibited in ("requests.post(", "fetch(", "urllib.request",
                       "httpx.post(", "github.com", "storage_state="):
        assert prohibited not in script
    assert 'save_failure(artifact_dir, key, old, new)' in script


def test_698_preview_uses_exact_pinned_checkout_and_disposable_data():
    preview = (ROOT / "scripts/tracker-preview698.sh").read_text()
    assert "BASE=6af8e4185fc76212f05d8a53cd4fec4043d804eb" in preview
    assert "REF=release/698-visual-regression" in preview
    assert "TRACKER_VISUAL_BASELINE_SHA" not in preview
    assert 'TRACKER_DATA_DIR="$BASE_DATA"' in preview
    assert 'TRACKER_DATA_DIR="$CANDIDATE_DATA"' in preview
    assert "git worktree add --detach" in preview
    assert "--baseline-url" in preview and "--candidate-url" in preview
    assert "tracker-release-scoped698.sh" in preview
    assert "RELEASE_698_PREVIEW_QUALIFIED" in preview
    assert "rm -rf --" in preview
    assert "TRACKER_698_TEST_BROWSER" in preview
