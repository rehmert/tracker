"""Release 685: meaningful compact spacing without clipping or undersized actions."""
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STYLE = (ROOT / "app/static/css/tracker-layout-density685.css").read_text()


def test_685_density_sheet_loaded_last_with_cache_busting():
    base = (ROOT / "app/templates/base.html").read_text()
    marker = '/static/css/tracker-layout-density685.css?v=685'
    assert base.count(marker) == 1
    assert base.index(marker) > base.index('tracker-workout-nav-density681.css?v=681')
    assert 'data-density="compact"' in STYLE
    assert 'data-density="balanced"' in STYLE
    assert "display: none" not in STYLE
    assert "font-size:" not in STYLE


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_685_usable_compact_density_and_theme(width):
    document = """<!doctype html><html data-density="comfortable"><head><style>
      * {box-sizing:border-box}
      body {margin:0;font:16px/1.4 sans-serif}
      #main-content {padding:12px;max-width:100%}
      .workspace-toolbar {margin:0 0 20px;padding:12px 0}
      .dashboard-hero {display:flex;flex-wrap:wrap;gap:20px;padding:10px 0 20px;margin-bottom:20px}
      .dashboard-hero .eyebrow {margin:0 0 12px}
      .dashboard-hero h1 {margin:0 0 12px}
      .dashboard-hero .hero-subtitle {margin:8px 0 12px}
      .dashboard-panel {margin:20px 0;padding:24px;border:1px solid}
      .section-intro {margin:16px 0;display:flex;gap:12px}
      .section-intro h2 {margin:8px 0}
      .tracker-ui-action {display:inline-flex;align-items:center;min-height:44px;padding:12px;border:1px solid}
      .tracker-status-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
      .tracker-status-card {padding:16px;border:1px solid}
    </style></head><body><main id="main-content">
      <div class="workspace-toolbar">Workspace tools</div>
      <header class="dashboard-hero">
        <div><p class="eyebrow">Personal health</p><h1>Overview</h1>
        <p class="hero-subtitle">Records and trends</p></div>
      </header>
      <section class="dashboard-panel">
        <div class="section-intro"><h2>At a glance</h2></div>
        <div class="tracker-status-grid">
          <div class="tracker-status-card">Stock value</div>
          <div class="tracker-status-card">Current status</div>
        </div>
        <a class="tracker-ui-action" href="#">Record dose</a>
      </section>
    </main></body></html>"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 850})
            page.set_content(document)
            page.add_style_tag(content=STYLE)
            def measurements(density):
                page.evaluate("(value) => document.documentElement.dataset.density = value", density)
                return page.evaluate("""() => {
                  const el = (selector) => document.querySelector(selector);
                  const rect = (selector) => el(selector).getBoundingClientRect();
                  const css = (selector) => getComputedStyle(el(selector));
                  return {
                    panelPad: parseFloat(css('.dashboard-panel').paddingTop),
                    panelMargin: parseFloat(css('.dashboard-panel').marginTop),
                    heroGap: parseFloat(css('.dashboard-hero').rowGap),
                    sectionMargin: parseFloat(css('.section-intro').marginBottom),
                    buttonHeight: rect('.tracker-ui-action').height,
                    buttonVisible: css('.tracker-ui-action').display !== 'none',
                    cardVisible: css('.tracker-status-card').display !== 'none',
                    scrollWidth: document.documentElement.scrollWidth
                  };
                }""")
            comfortable = measurements("comfortable")
            balanced = measurements("balanced")
            compact = measurements("compact")
            assert compact["panelPad"] < balanced["panelPad"] < comfortable["panelPad"]
            assert compact["panelMargin"] < comfortable["panelMargin"]
            assert compact["heroGap"] < comfortable["heroGap"]
            assert compact["sectionMargin"] < comfortable["sectionMargin"]
            assert compact["buttonHeight"] >= 44
            assert compact["buttonVisible"] and compact["cardVisible"]
            assert compact["scrollWidth"] <= width + 1
        finally:
            browser.close()
