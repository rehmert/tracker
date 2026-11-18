"""Release 686: compare actual layout against Release 685, preserve usable targets."""
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS685 = (ROOT / "app/static/css/tracker-layout-density685.css").read_text()
CSS686 = (ROOT / "app/static/css/tracker-compact-aggressive686.css").read_text()
BASE = (ROOT / "app/templates/base.html").read_text()
DOC = """<!doctype html><html data-density="compact"><head><style>
*{box-sizing:border-box}body{margin:0;font:16px/1.4 sans-serif}
#main-content{padding:12px;max-width:100%}
.workspace-toolbar{margin:0 0 20px;padding:12px 0}
.dashboard-hero{display:flex;flex-wrap:wrap;gap:20px;padding:10px 0 20px;margin-bottom:20px}
.dashboard-hero .eyebrow{margin:0 0 12px}
.dashboard-hero h1{margin:0 0 12px}
.dashboard-hero .hero-subtitle{margin:8px 0 12px}
.dashboard-panel{margin:20px 0;padding:24px;border:1px solid}
.section-intro{margin:16px 0;display:flex;gap:12px}
.section-intro h2{margin:8px 0}
.tracker-ui-action{display:inline-flex;align-items:center;min-height:44px;padding:12px;border:1px solid}
.tracker-status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.tracker-status-card{padding:16px;border:1px solid}
.recon-vial-picker{padding:16px;margin:16px 0}
.recon .card{padding:16px}
</style></head><body><main id="main-content">
<div class="workspace-toolbar">Workspace tools</div>
<header class="dashboard-hero"><div><p class="eyebrow">Personal health</p>
<h1>Overview</h1><p class="hero-subtitle">Records and trends</p></div></header>
<section class="dashboard-panel">
<div class="section-intro"><h2>At a glance</h2></div>
<div class="tracker-status-grid">
<div class="tracker-status-card">Stock value</div>
<div class="tracker-status-card">Current status</div></div>
<a class="tracker-ui-action" href="#">Record dose</a></section>
<div class="recon"><form class="recon-vial-picker"><label>Vial</label><select><option>Lot 686</option></select></form>
<div class="card">Reconstitution controls</div></div>
</main></body></html>"""


def test_686_is_last_and_is_compact_only():
    assert BASE.count("/static/css/tracker-compact-aggressive686.css?v=686") == 1
    assert BASE.index("tracker-layout-density685.css?v=685") < BASE.index(
        "tracker-compact-aggressive686.css?v=686")
    assert ':root[data-density="compact"]' in CSS686
    assert 'data-density="balanced"' not in CSS686
    assert 'data-density="comfortable"' not in CSS686
    assert "display: none" not in CSS686
    assert "font-size:" not in CSS686


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_686_is_measurably_tighter_than_685_without_clipping(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.set_content(DOC)
            page.add_style_tag(content=CSS685)
            def sample(density):
                page.evaluate("(d) => document.documentElement.dataset.density = d",density)
                return page.evaluate("""() => {
                    const c=s=>getComputedStyle(document.querySelector(s));
                    const r=s=>document.querySelector(s).getBoundingClientRect();
                    return {
                      toolbarMargin:parseFloat(c('.workspace-toolbar').marginBottom),
                      panelPad:parseFloat(c('.dashboard-panel').paddingTop),
                      panelMargin:parseFloat(c('.dashboard-panel').marginTop),
                      statusGap:parseFloat(c('.tracker-status-grid').gap),
                      reconPad:parseFloat(c('.recon-vial-picker').paddingTop),
                      actionHeight:r('.tracker-ui-action').height,
                      actionVisible:c('.tracker-ui-action').display!=='none',
                      contentVisible:c('.tracker-status-card').display!=='none',
                      fontSize:parseFloat(c('.tracker-status-card').fontSize),
                      scrollWidth:document.documentElement.scrollWidth
                    };
                }""")
            before={d:sample(d) for d in ("compact","balanced","comfortable")}
            page.add_style_tag(content=CSS686)
            after={d:sample(d) for d in ("compact","balanced","comfortable")}
            for key in ("toolbarMargin","panelPad","panelMargin","statusGap","reconPad"):
                assert after["compact"][key] < before["compact"][key], (
                    width,key,before["compact"][key],after["compact"][key])
            assert after["compact"]["panelPad"] <= before["compact"]["panelPad"]*.7
            assert after["compact"]["actionHeight"] >= 44
            assert after["compact"]["actionVisible"] and after["compact"]["contentVisible"]
            assert after["compact"]["fontSize"] == before["compact"]["fontSize"]
            assert after["compact"]["scrollWidth"] <= width+1
            for d in ("balanced","comfortable"):
                assert before[d] == after[d], (width,d,before[d],after[d])
        finally:
            browser.close()
