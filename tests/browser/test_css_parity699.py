"""Release 699: identical CSS computed styles + pixels at three densities.

Uses the exact detached Release 698 baseline and candidate CSS directories
provided ONLY by the local isolated preview. Does not load network pages.
"""
from io import BytesIO
from pathlib import Path
import os

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.environ.get("TRACKER_CSS_PARITY699") != "1",
    reason="Only run with pinned baseline and candidate worktrees in isolated preview",
)
SHEETS = ("tracker-layout-density685.css", "tracker-compact-aggressive686.css")
WIDTHS = (320, 390, 768, 1280, 1920)
DENSITIES = ("compact", "balanced", "comfortable")
THEMES = ("light", "dark")
CSS_FIXTURE = """
* { box-sizing:border-box; }
body { margin:0; font:16px/1.4 sans-serif; }
main { display:block; max-width:100%; padding:12px; }
.workspace-toolbar { margin:0 0 20px; padding:12px 0; }
.dashboard-hero,.page-header { display:flex;flex-wrap:wrap; gap:20px;
  padding:10px 0 20px; margin-bottom:20px; }
.dashboard-hero .eyebrow,.page-header .eyebrow { margin:0 0 12px; }
.dashboard-hero h1,.page-header h1 { margin:0 0 12px; }
.dashboard-panel { margin:20px 0; padding:24px; border:1px solid; }
.section-intro,.panel-heading { margin:16px 0; display:flex;gap:12px; }
.section-intro h2,.panel-heading h3 { margin:8px 0; }
.tracker-ui-card,.ux673-card,.insight-card,.inventory-card,
.today-card,.protocol-card,.export-card,.tracker-status-card {
 padding:16px;border:1px solid; margin:4px 0;
}
.tracker-status-grid,.inventory-kpis,.today-cards { display:grid;
 grid-template-columns:repeat(2,minmax(0,1fr));gap:12px; }
.tracker-ui-action,.ux673-action-row > a,.ux673-action-row > button,
.tracker-daily-actions a,.tracker-daily-mode button,
.tracker-daily-list li a {
 display:inline-flex;align-items:center;justify-content:center;
 min-height:44px; padding:8px; border:1px solid; }
.recon-vial-picker,.recon .card,.recon-metric { padding:16px; margin:16px 0; }
.page-header { margin-top:12px; }
.grid,.inline,.cards { display:flex; gap:12px; flex-wrap:wrap; }
.tracker-daily-section { padding:14px; }
.chartbox { padding:12px; }
#main-content :is(h2,h3) { font-size:1.15rem; }
"""
HTML = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head><body><main id="main-content">
<div class="workspace-toolbar">Account · Search · Preferences</div>
<header class="dashboard-hero">
 <p class="eyebrow">Small heading</p><h1>Dashboard</h1>
 <p class="hero-subtitle">Summary</p>
</header>
<section class="dashboard-panel">
 <div class="section-intro"><h2>Section title</h2></div>
 <div class="tracker-status-grid">
  <div class="tracker-status-card">Status A</div>
  <div class="tracker-status-card">Status B</div>
 </div>
 <div class="cards">
  <div class="tracker-ui-card">Shared UI</div>
  <div class="ux673-card">Mobile card</div>
  <div class="insight-card">Insight</div>
  <div class="inventory-card">Inventory</div>
  <div class="today-card">Today</div>
  <div class="protocol-card">Protocol</div>
  <div class="export-card">Export</div>
 </div>
 <div class="ux673-action-row">
  <a href="#">Log</a><button>Record</button>
 </div>
 <a href="#" class="tracker-ui-action">Shared action</a>
 <nav class="tracker-daily-actions"><a href="#">Record Vitals</a></nav>
 <div class="tracker-daily-mode"><button>Mode</button></div>
 <ul class="tracker-daily-list"><li><a href="#">Recorded</a></li></ul>
</section>
<header class="page-header"><div class="eyebrow">Page eyebrow</div>
<h1>Other header</h1><p class="description">Details</p></header>
<div class="panel-heading"><h3>Panel Heading</h3></div>
<div class="grid"><div>Grid item</div><div>Grid item 2</div></div>
<div class="recon">
 <div class="recon-vial-picker"><label>Vial <select><option>Stock</option></select></label></div>
 <div class="card">Reconstitution</div>
 <div class="recon-metric">Metric</div>
</div>
<div class="chartbox">Chart container</div>
</main></body></html>"""
SELECTORS = (
    "#main-content", ".workspace-toolbar", ".dashboard-hero", ".page-header",
    ".dashboard-hero .eyebrow", ".page-header .eyebrow",
    ".dashboard-hero h1", ".page-header h1",
    ".dashboard-panel", ".section-intro", ".panel-heading",
    ".section-intro h2", ".panel-heading h3",
    ".tracker-status-grid", ".tracker-status-card", ".tracker-ui-card",
    ".ux673-card", ".insight-card", ".inventory-card", ".today-card",
    ".protocol-card", ".export-card", ".tracker-ui-action",
    ".ux673-action-row > a", ".ux673-action-row > button",
    ".tracker-daily-actions a", ".tracker-daily-mode button",
    ".tracker-daily-list li a", ".recon-vial-picker", ".recon .card",
    ".recon-metric", ".chartbox",
)
PROPERTIES = (
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "marginTop", "marginRight", "marginBottom", "marginLeft",
    "rowGap", "columnGap", "minHeight", "minWidth", "lineHeight",
    "fontSize", "display", "gridTemplateColumns",
)


def stylesheet_root(name: str) -> Path:
    path = Path(os.environ[name]).resolve()
    # The separately pinned worktrees exist only beneath our disposable
    # visual preview; fail rather than silently reading installed sources.
    if not str(path).startswith("/tmp/tracker-preview699."):
        raise AssertionError("CSS comparison must use private isolated preview roots")
    if path.name != "css" or not path.is_dir():
        raise AssertionError("CSS path must be an existing static css directory")
    return path


def css(root: Path, include686: bool) -> list[str]:
    sheets = SHEETS if include686 else SHEETS[:1]
    return [(root / sheet).read_text(encoding="utf-8") for sheet in sheets]


def metrics(page):
    return page.evaluate("""(selectors) => {
      const props = %s;
      return selectors.map(selector => {
        const el = document.querySelector(selector);
        if (!el) throw Error('Missing parity fixture element: ' + selector);
        const computed = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return {
          selector,
          css: props.map(prop => computed[prop]),
          bounds: [rect.width, rect.height, rect.top, rect.left]
            .map(value => Math.round(value * 100) / 100),
        };
      });
    }""" % repr(list(PROPERTIES)), list(SELECTORS))


def screenshot(page):
    return page.screenshot(animations="disabled", caret="hide")


def render(page, root: Path, include686: bool, density: str, theme: str):
    page.set_content(HTML)
    page.evaluate("(values) => { document.documentElement.dataset.density=values[0]; document.documentElement.dataset.theme=values[1]; }", [density, theme])
    page.add_style_tag(content=CSS_FIXTURE)
    page.add_style_tag(content=(
        ":root{--surface:#fff;--ink:#172b39;--rule:#b4c3d2;--teal:#1265ad}"
        if theme == "light" else
        ":root{--surface:#172b39;--ink:#f1f5f9;--rule:#526779;--teal:#78baff;"
        "background:#172b39;color:#f1f5f9}"
    ))
    for text in css(root, include686):
        page.add_style_tag(content=text)
    return metrics(page), screenshot(page)


def test_699_standalone_and_combined_css_are_pixel_and_style_identical():
    before = stylesheet_root("TRACKER_699_BASE_CSS")
    after = stylesheet_root("TRACKER_699_CANDIDATE_CSS")
    assert before != after
    comparisons = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
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
                        reference = context.new_page()
                        candidate = context.new_page()
                        for density in DENSITIES:
                            for combined in (False, True):
                                label = f"{width}:{theme}:{density}:{'685+686' if combined else '685'}"
                                ref_metrics, ref_png = render(reference, before, combined, density, theme)
                                new_metrics, new_png = render(candidate, after, combined, density, theme)
                                assert new_metrics == ref_metrics, f"Computed CSS changed: {label}"
                                with Image.open(BytesIO(ref_png)) as a, Image.open(BytesIO(new_png)) as b:
                                    assert ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None, (
                                        f"Pixels changed: {label}"
                                    )
                                assert candidate.evaluate(
                                    "() => document.documentElement.scrollWidth <= innerWidth + 1"
                                ), f"Horizontal overflow: {label}"
                                comparisons += 1
                    finally:
                        context.close()
        finally:
            browser.close()
    assert comparisons == len(WIDTHS) * len(THEMES) * len(DENSITIES) * 2
    print(f"RELEASE_699_CSS_PARITY_COMPARISONS={comparisons}")
    print("RELEASE_699_CSS_COMPUTED_AND_PIXELS=IDENTICAL")
