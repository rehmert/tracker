"""Release 687: desktop Compact shortcuts and top-bar regression."""
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "app/templates/base.html").read_text()
DASH = (ROOT / "app/templates/dashboard.html").read_text()
STYLE = (ROOT / "app/static/css/tracker-shortcuts-toolbar687.css").read_text()
DAILY = (ROOT / "app/static/css/tracker-daily-flow559.css").read_text()
WORKSPACE = (ROOT / "app/static/workspace_toolbar.js").read_text()


def test_687_markup_and_asset_contract():
    assert BASE.count('/static/css/tracker-global-density-bundle746.css?v=746') == 1
    assert 'class="tracker-account-action687">Accounts</a>' in BASE
    assert '<a href="/account/security" class="tracker-account-action687">' in BASE
    assert 'Account Security\n' not in BASE
    assert '<details class="workspace-recent" id="tracker-recent-pages" hidden>' in BASE
    assert 'id="workspace-settings-toggle"' in BASE
    assert 'Your Daily Shortcuts' in DASH
    assert 'min-height: 44px' in STYLE


HTML = """<!doctype html><html data-density="compact"><head><style>
*{box-sizing:border-box}
body{margin:0;font:16px/1.4 sans-serif}
#main-content{width:100%;padding:8px}
.workspace-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.workspace-toolbar>form{display:inline-flex}
.workspace-search{min-width:240px;padding:9px}
.workspace-nav-find{min-width:230px;flex:0 1 230px}
.workspace-nav-find input{width:100%;height:40px}
.workspace-settings{position:relative;margin-left:auto}
.workspace-settings-panel{position:absolute;right:0;top:100%;width:260px;background:white;z-index:5}
.workspace-settings-panel[hidden]{display:none!important}
.workspace-recent{display:block}
.tracker-daily-flow559 {margin:16px 0 22px;padding:16px;border:1px solid}
.tracker-daily-flow559-head h2{margin:0 0 3px}
.tracker-daily-flow559-head p{margin:0 0 13px}
.tracker-daily-flow559-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:9px}
.tracker-daily-flow559-links a{display:flex;flex-direction:column;gap:3px;padding:12px;border:1px solid;text-decoration:none}
</style></head><body><main id="main-content">
<div class="workspace-toolbar">
<a href="/account/security" class="tracker-account-action687">Accounts</a>
<form><button type="button">Sign Out</button></form>
<div class="ux-add-menu"><button type="button">+ Add</button></div>
<button class="workspace-search" type="button">Search Tracker</button>
<div class="workspace-nav-find"><input type="search" aria-label="Find page"></div>
<details class="workspace-recent" id="tracker-recent-pages" hidden><summary>Recent Pages</summary></details>
<div class="workspace-settings" id="workspace-settings">
<button id="workspace-settings-toggle" aria-expanded="false" aria-controls="workspace-settings-panel" type="button">Preferences</button>
<section class="workspace-settings-panel" id="workspace-settings-panel" hidden>
<button type="button" id="workspace-settings-close">Close</button>Preferences content
</section></div></div>
<section class="tracker-daily-flow559"><div class="tracker-daily-flow559-head">
<h2>Your Daily Shortcuts</h2><p>Record the essentials or jump to information.</p></div>
<nav class="tracker-daily-flow559-links" aria-label="Everyday workflow shortcuts">
<a href="/mobile"><strong>Today</strong><span>Readings and schedule</span></a>
<a href="/doses"><strong>Log Dose</strong><span>Record actual use</span></a>
<a href="/vitals"><strong>Log Vitals</strong><span>Weight, BP, pulse</span></a>
<a href="/food"><strong>Log Food</strong><span>Favorite meals and foods</span></a>
<a href="/water"><strong>Log Water</strong><span>Daily hydration</span></a>
<a href="/calendar"><strong>Calendar</strong><span>Review scheduled items</span></a>
</nav></section></main></body></html>"""


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440, 1920])
def test_687_compact_shortcuts_and_toolbar(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width":width,"height":900})
            page.set_content(HTML)
            page.add_style_tag(content=DAILY)
            def metrics():
                return page.evaluate("""() => {
                    const q=s=>document.querySelector(s);
                    const cs=s=>getComputedStyle(q(s));
                    const rect=s=>q(s).getBoundingClientRect();
                    return {
                        sectionPadding:parseFloat(cs('.tracker-daily-flow559').paddingTop),
                        tilePadding:parseFloat(cs('.tracker-daily-flow559-links a').paddingTop),
                        tileGap:parseFloat(cs('.tracker-daily-flow559-links').columnGap),
                        tileHeight:rect('.tracker-daily-flow559-links a').height,
                        accountUnderline:cs('.tracker-account-action687').textDecorationLine,
                        accountHeight:rect('.tracker-account-action687').height,
                        recentShown:cs('#tracker-recent-pages').display!=='none',
                        toolbarY:rect('.workspace-toolbar').y,
                        accountY:rect('.tracker-account-action687').y,
                        preferenceY:rect('#workspace-settings-toggle').y,
                        overflow:document.documentElement.scrollWidth>innerWidth+1
                    };
                }""")
            before=metrics()
            page.add_style_tag(content=STYLE)
            after=metrics()
            assert after["sectionPadding"] <= 5, (width,after)
            assert after["tilePadding"] < before["tilePadding"]*.4, (width,before,after)
            assert after["tileGap"] < before["tileGap"], (width,before,after)
            assert after["tileHeight"] >= (44 if width<=760 else 40), (width,after)
            assert after["accountUnderline"]=="none"
            assert after["accountHeight"] >= (44 if width<=760 else 40)
            assert not after["recentShown"]
            if width >= 768:
                assert after["preferenceY"] < after["accountY"]+50, (width,after)
            else:
                assert after["preferenceY"] < after["accountY"]+110, (width,after)
            assert not after["overflow"], (width,after)
            page.add_script_tag(content=WORKSPACE)
            page.locator("#workspace-settings-toggle").click()
            assert page.locator("#workspace-settings-panel").is_visible()
            page.locator("#workspace-settings-close").click()
            assert page.locator("#workspace-settings-panel").is_hidden()
        finally:
            browser.close()
