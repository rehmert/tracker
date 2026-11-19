"""Release 700: deterministic Chromium computed-style and zero-pixel CSS parity.

Render pinned Release 699 fixture once, snapshot its stable pixels, then
change ONLY the live Release 687 style element to candidate CSS in place.
Never recreate the DOM or browser focus state between the A/B screenshots.
No authentication, external assets, live data or golden images.
"""
from io import BytesIO
from pathlib import Path
import os

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.environ.get("TRACKER_CSS_PARITY700") != "1",
    reason="Run only in guarded Release 700 isolated preview with both source roots",
)
WIDTHS = (320, 390, 768, 1280, 1920)
DENSITIES = ("compact", "balanced", "comfortable")
THEMES = ("light", "dark")
MODES = ("toolbar687", "combined")
STABLE_STYLE = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  caret-color: transparent !important;
}
"""

# Real application styles, in the relevant applied order for the Dashboard.
COMMON = (
    "app/static/app.css",
    "app/static/css/tracker-layout-density685.css",
    "app/static/css/tracker-compact-aggressive686.css",
)
TOOLBAR = "app/static/css/tracker-shortcuts-toolbar687.css"
ADDITIONAL = (
    "app/static/css/tracker-dashboard-polish688.css",
    "app/static/css/tracker-workout-footnote689.css",
    "app/static/css/tracker-workout-dashboard661.css",
    "app/static/css/tracker-daily-flow559.css",
    "app/static/css/tracker-overview-density690.css",
)

HTML = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head><body><main id="main-content">
<div class="workspace-toolbar">
  <a class="tracker-account-action687" href="/account/security">Accounts</a>
  <form><button type="button">Sign Out</button></form>
  <div class="ux-add-menu"><button type="button" id="ux-add-toggle">+ Add</button></div>
  <button type="button" class="workspace-search" id="command-open">
    <span>Search Tracker</span><kbd>Ctrl K</kbd>
  </button>
  <div class="workspace-nav-find" id="page-finder-container">
    <div class="nav-find"><input id="nav-filter" aria-label="Find a page"></div>
  </div>
  <div class="workspace-settings">
    <button type="button" id="workspace-settings-toggle">Preferences</button>
  </div>
</div>
<div id="tracker-page-jump-slot">
  <nav class="tracker-page-jump">
   <label for="tracker-page-jump-select">Sections
     <select id="tracker-page-jump-select"><option>Overview</option></select>
   </label>
   <button type="button" class="tracker-copy-section-link">Copy Link</button>
  </nav>
</div>
<section class="tracker-daily-flow559">
  <div class="tracker-daily-flow559-head">
    <h2>Your Daily Shortcuts</h2><p>Record the essentials</p>
  </div>
  <nav class="tracker-daily-flow559-links" aria-label="Everyday workflow shortcuts">
    <a href="/mobile"><strong>Today</strong></a>
    <a href="/doses"><strong>Log Dose</strong></a>
    <a href="/vitals"><strong>Log Vitals</strong></a>
    <a href="/food"><strong>Log Food</strong></a>
    <a href="/workouts"><strong>Workout</strong></a>
  </nav>
</section>
<section id="tracker-workout-dashboard661">
  <div class="tracker-workout-summary661">
    <div><strong>5</strong><span>Workouts</span></div>
    <div><strong>30</strong><span>Sets</span></div>
    <div><strong>2</strong><span>Weeks</span></div>
    <div><strong>1</strong><span>Month</span></div>
    <div><strong>9</strong><span>Days</span></div>
    <div><strong>40</strong><span>Reps</span></div>
  </div>
  <div class="tracker-workout-recent661">
    <h3>Recent</h3><p><a class="tracker-workout-empty-action678" href="#">Log a Previous Workout</a></p>
  </div>
  <p class="tracker-workout-footnote661">A training day is a calendar date</p>
</section>
</main></body></html>"""

SELECTORS = (
    ".workspace-toolbar",
    ".tracker-account-action687",
    ".workspace-toolbar form button",
    "#ux-add-toggle",
    "#command-open",
    "#nav-filter",
    ".workspace-nav-find",
    "#workspace-settings-toggle",
    ".tracker-page-jump",
    ".tracker-page-jump label",
    "#tracker-page-jump-select",
    ".tracker-copy-section-link",
    ".tracker-daily-flow559",
    ".tracker-daily-flow559-head",
    ".tracker-daily-flow559-links",
    ".tracker-daily-flow559-links a",
    ".tracker-daily-flow559-links a strong",
    ".tracker-workout-summary661",
    ".tracker-workout-summary661 > div",
    ".tracker-workout-empty-action678",
    ".tracker-workout-footnote661",
)
PROPS = (
    "boxSizing", "display", "height", "minHeight", "maxHeight",
    "width", "minWidth", "maxWidth", "flex", "flexWrap",
    "alignItems", "justifyContent", "order",
    "gridTemplateColumns", "gap", "rowGap", "columnGap",
    "marginTop", "marginRight", "marginBottom", "marginLeft",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "fontFamily", "fontSize", "fontWeight", "lineHeight",
    "color", "backgroundColor", "borderTopWidth", "borderTopStyle",
    "borderTopLeftRadius", "textAlign", "textDecorationLine",
    "outlineStyle", "outlineWidth",
)


def css_root(name: str) -> Path:
    raw = Path(os.environ[name])
    if not raw.is_absolute() or raw.is_symlink():
        raise AssertionError("CSS source root must be an absolute, non-symlink path")
    root = raw.resolve()
    if "/tmp/tracker-preview700." not in str(root) or root.name not in ("baseline", "candidate"):
        raise AssertionError("CSS must be in an isolated Release 700 source worktree")
    if not root.is_dir():
        raise AssertionError("CSS source worktree is missing")
    return root


def sheet(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def verify_unmodified_css(baseline: Path, candidate: Path) -> None:
    """Every non-687 stylesheet must be byte-identical across both sources."""
    for name in COMMON + ADDITIONAL:
        assert sheet(baseline, name) == sheet(candidate, name), (
            f"Non-target stylesheet changed unexpectedly: {name}"
        )


def measured(page):
    return page.evaluate("""(selectors) => {
        const props = %s;
        const list = selectors.map(selector => {
          const element = document.querySelector(selector);
          if (!element) throw Error('Missing fixture element: ' + selector);
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return {
            selector,
            css: props.map(key => style[key]),
            bounds: [rect.x,rect.y,rect.width,rect.height]
              .map(value => Math.round(value*100)/100)
          };
        });
        return {
          list,
          overflow: Math.max(0, document.documentElement.scrollWidth - innerWidth)
        };
    }""" % repr(list(PROPS)), list(SELECTORS))


def settle(page):
    # Keep DOM, focus state, scroll position, and all non-target styles fixed.
    page.evaluate("() => document.fonts.ready")
    page.evaluate("""() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)))""")


def render_fixture(page, baseline: Path, theme: str, density: str, mode: str):
    """One initial render. Return the ONLY style element allowed to change."""
    page.set_content(HTML)
    page.evaluate("""([theme,density]) => {
      document.documentElement.dataset.theme=theme;
      document.documentElement.dataset.density=density;
    }""", [theme, density])
    palette = (
        ":root{--surface:#fff;--ink:#172b39;--rule:#bdc8d4;"
        "--wash:#eef4f8;--teal:#1265ad;--teal-ink:#fff}"
        if theme == "light" else
        ":root{background:#172b39;color:#f0f5fa;--surface:#172b39;"
        "--ink:#f0f5fa;--rule:#526779;--wash:#263645;"
        "--teal:#78baff;--teal-ink:#091725}"
    )
    page.add_style_tag(content=palette)
    for name in COMMON:
        page.add_style_tag(content=sheet(baseline, name))
    target_style = page.add_style_tag(content=sheet(baseline, TOOLBAR))
    if mode == "combined":
        for name in ADDITIONAL:
            page.add_style_tag(content=sheet(baseline, name))
    page.add_style_tag(content=STABLE_STYLE)
    page.locator("#command-open").focus()
    page.evaluate("() => window.scrollTo(0, 0)")
    settle(page)
    return target_style


def capture(page):
    settle(page)
    return measured(page), page.screenshot(animations="disabled", caret="hide")


def save_private_diff(label: str, original: bytes, current: bytes) -> None:
    """Retain synthetic fixture evidence locally on DEV only, on failure."""
    folder_name = os.environ.get("TRACKER_700_PARITY_ARTIFACT_DIR")
    if not folder_name:
        return
    folder = Path(folder_name)
    if (not folder.is_absolute() or folder.is_symlink()
            or folder.name != "visual-failures"
            or "/tmp/tracker-preview700." not in str(folder)):
        raise AssertionError("Refusing non-private CSS parity artifact path")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    safe = label.replace(":", "-")
    if not safe.replace("-", "").isalnum():
        raise AssertionError("Unexpected CSS parity artifact filename")
    (folder / f"{safe}-baseline.png").write_bytes(original)
    (folder / f"{safe}-candidate.png").write_bytes(current)
    with Image.open(BytesIO(original)) as left, Image.open(BytesIO(current)) as right:
        ImageChops.difference(left.convert("RGB"), right.convert("RGB")).save(
            folder / f"{safe}-diff.png"
        )
    for file in folder.glob(f"{safe}-*.png"):
        file.chmod(0o600)


def test_700_exact_rendered_toolbar_shortcuts_and_workout_parity():
    baseline = css_root("TRACKER_700_BASE_SOURCE")
    candidate = css_root("TRACKER_700_CANDIDATE_SOURCE")
    assert baseline != candidate
    verify_unmodified_css(baseline, candidate)
    original_css = sheet(baseline, TOOLBAR)
    replacement_css = sheet(candidate, TOOLBAR)
    assert original_css != replacement_css, "No Release 687 CSS change to qualify"
    comparisons = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            for width in WIDTHS:
                for theme in THEMES:
                    context = browser.new_context(
                        viewport={"width": width, "height": 900},
                        device_scale_factor=1,
                        color_scheme=theme,
                        reduced_motion="reduce",
                    )
                    try:
                        context.route("**/*", lambda route: route.abort())
                        page = context.new_page()
                        for density in DENSITIES:
                            for mode in MODES:
                                label = f"{width}:{theme}:{density}:{mode}"
                                target_style = render_fixture(
                                    page, baseline, theme, density, mode
                                )
                                # Two images of the exact same untouched DOM.
                                a, img_a = capture(page)
                                stable, img_stable = capture(page)
                                assert a == stable, f"Baseline geometry unstable: {label}"
                                with Image.open(BytesIO(img_a)) as first, Image.open(BytesIO(img_stable)) as second:
                                    jitter = ImageChops.difference(
                                        first.convert("RGB"), second.convert("RGB")
                                    ).getbbox()
                                if jitter is not None:
                                    save_private_diff(
                                        label + ":baseline-instability", img_a, img_stable
                                    )
                                assert jitter is None, (
                                    f"Baseline screenshot not deterministic: {label} bbox={jitter}"
                                )

                                # CSS-only A/B: retain the EXACT same DOM,
                                # focused control, scroll position and all
                                # non-target styles, changing one style tag.
                                target_style.evaluate(
                                    "(node, css) => { node.textContent = css; }",
                                    replacement_css
                                )
                                b, img_b = capture(page)
                                assert a == b, f"Computed style/geometry changed: {label}"
                                with Image.open(BytesIO(img_a)) as first, Image.open(BytesIO(img_b)) as second:
                                    bbox = ImageChops.difference(
                                        first.convert("RGB"), second.convert("RGB")
                                    ).getbbox()
                                if bbox is not None:
                                    save_private_diff(label, img_a, img_b)
                                assert bbox is None, f"Screenshot changed: {label} bbox={bbox}"
                                assert b["overflow"] == a["overflow"], (
                                    f"Horizontal overflow changed: {label}"
                                )

                                # Round-trip the CSS. If source replacement
                                # itself changed paint state irreversibly,
                                # fail rather than misreport exact equality.
                                target_style.evaluate(
                                    "(node, css) => { node.textContent = css; }",
                                    original_css
                                )
                                roundtrip, img_roundtrip = capture(page)
                                assert a == roundtrip, (
                                    f"CSS round-trip geometry changed: {label}"
                                )
                                with Image.open(BytesIO(img_a)) as first, Image.open(BytesIO(img_roundtrip)) as second:
                                    roundtrip_bbox = ImageChops.difference(
                                        first.convert("RGB"), second.convert("RGB")
                                    ).getbbox()
                                if roundtrip_bbox is not None:
                                    save_private_diff(
                                        label + ":css-roundtrip", img_a, img_roundtrip
                                    )
                                assert roundtrip_bbox is None, (
                                    f"CSS round-trip pixels changed: {label} "
                                    f"bbox={roundtrip_bbox}"
                                )
                                comparisons += 1
                    finally:
                        context.close()
        finally:
            browser.close()
    assert comparisons == len(WIDTHS) * len(THEMES) * len(DENSITIES) * len(MODES)
    print(f"RELEASE_700_CSS_PARITY_COMPARISONS={comparisons}")
    print("RELEASE_700_CSS_COMPUTED_AND_PIXELS=IDENTICAL")
