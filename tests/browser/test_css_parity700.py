"""Release 700: deterministic Chromium CSS and pixel parity for shared UI.

Compare pinned Release 699 and candidate source in one active browser tab,
resetting the same fixture between renders to avoid cross-tab focus paint
variance. No authentication, external assets, user data or golden images.
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


def css_sources(root: Path, mode: str) -> list[str]:
    names = COMMON + (TOOLBAR,)
    if mode == "combined":
        names += ADDITIONAL
    return [(root / name).read_text(encoding="utf-8") for name in names]


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


def render(page, root: Path, width: int, theme: str, density: str, mode: str):
    page.set_content(HTML)
    page.evaluate("""([theme,density]) => {
      document.documentElement.dataset.theme=theme;
      document.documentElement.dataset.density=density;
    }""", [theme, density])
    # Minimal declared theme tokens; source CSS remains unmodified.
    palette = (
        ":root{--surface:#fff;--ink:#172b39;--rule:#bdc8d4;"
        "--wash:#eef4f8;--teal:#1265ad;--teal-ink:#fff}"
        if theme == "light" else
        ":root{background:#172b39;color:#f0f5fa;--surface:#172b39;"
        "--ink:#f0f5fa;--rule:#526779;--wash:#263645;"
        "--teal:#78baff;--teal-ink:#091725}"
    )
    page.add_style_tag(content=palette)
    for source in css_sources(root, mode):
        page.add_style_tag(content=source)
    # Force an identical focus state in the same foreground page for both
    # sources. Separate tabs can paint the active focus outline differently
    # even when all computed styles and element bounds match.
    page.add_style_tag(content=STABLE_STYLE)
    page.locator("#command-open").focus()
    page.evaluate("() => document.fonts.ready")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.evaluate("""() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)))""")
    return measured(page), page.screenshot(animations="disabled", caret="hide")


def test_700_exact_rendered_toolbar_shortcuts_and_workout_parity():
    baseline = css_root("TRACKER_700_BASE_SOURCE")
    candidate = css_root("TRACKER_700_CANDIDATE_SOURCE")
    assert baseline != candidate
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
                        # The same tab renders baseline and candidate in turn;
                        # unlike two concurrent tabs, focus/foreground state
                        # cannot diverge. Abort external assets entirely.
                        context.route("**/*", lambda route: route.abort())
                        page = context.new_page()
                        for density in DENSITIES:
                            for mode in MODES:
                                label = f"{width}:{theme}:{density}:{mode}"
                                a, img_a = render(page, baseline, width, theme, density, mode)
                                # Validate our baseline screenshot is stable
                                # before judging any candidate-side difference.
                                stable, img_stable = render(
                                    page, baseline, width, theme, density, mode
                                )
                                assert a == stable, f"Baseline geometry unstable: {label}"
                                with Image.open(BytesIO(img_a)) as first, Image.open(BytesIO(img_stable)) as second:
                                    jitter = ImageChops.difference(
                                        first.convert("RGB"), second.convert("RGB")
                                    ).getbbox()
                                assert jitter is None, (
                                    f"Baseline screenshot not deterministic: {label} bbox={jitter}"
                                )
                                b, img_b = render(
                                    page, candidate, width, theme, density, mode
                                )
                                assert a == b, f"Computed style/geometry changed: {label}"
                                with Image.open(BytesIO(img_a)) as left, Image.open(BytesIO(img_b)) as right:
                                    difference = ImageChops.difference(
                                        left.convert("RGB"), right.convert("RGB")
                                    )
                                    bbox = difference.getbbox()
                                    assert bbox is None, f"Screenshot changed: {label} bbox={bbox}"
                                assert b["overflow"] == a["overflow"], (
                                    f"Horizontal overflow changed: {label}"
                                )
                                comparisons += 1
                    finally:
                        context.close()
        finally:
            browser.close()
    assert comparisons == len(WIDTHS) * len(THEMES) * len(DENSITIES) * len(MODES)
    print(f"RELEASE_700_CSS_PARITY_COMPARISONS={comparisons}")
    print("RELEASE_700_CSS_COMPUTED_AND_PIXELS=IDENTICAL")
