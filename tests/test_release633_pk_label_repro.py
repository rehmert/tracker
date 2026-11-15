"""Release 633: navigation, label print guidance, and reproducibility contracts.

These checks only inspect candidate source. They never run browser suites,
download packages, launch a deployer or contact a printer.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_pk_fast_path_retains_existing_simulation_controls():
    html = source("app/templates/pk.html")
    Environment().parse(html)
    for mode, dest in (
        ("protocol", "pkSetup"),
        ("custom", "whatIfCard"),
    ):
        assert f'data-pk633-jump="{dest}" data-pk633-mode="{mode}"' in html
    assert 'data-pk633-jump="pkResults"' in html
    assert 'id="pk633NavStatus"' in html
    for legacy in ("protocol", "compound", "refresh", "plot", "wiPreview",
                   "compareBtn", "pkResults"):
        assert f'id="{legacy}"' in html
    assert 'tracker-pk-fast633.js?v=633' in html
    assert 'tracker-pk-fast633.css?v=633' in html


def test_pk_navigation_is_read_only_and_reuses_current_tab_logic():
    js = source("app/static/js/tracker-pk-fast633.js")
    css = source("app/static/css/tracker-pk-fast633.css")
    assert "tab.click()" in js
    assert "scrollIntoView" in js
    assert "textContent" in js
    for forbidden in ("fetch(", "XMLHttpRequest", "localStorage",
                      "sessionStorage", "innerHTML", "form.submit("):
        assert forbidden not in js
    assert "prefers-reduced-motion" not in css or "scroll-behavior:auto" in css


def test_niimbot_dimensions_and_print_checklist_on_both_label_views():
    js = source("app/static/js/tracker-label-print-guide633.js")
    assert '"40x20"' in js and '"30x15x2"' in js and '"10x20x4"' in js
    assert '"320 × 160"' in js and '"240 × 240"' in js
    assert "fetch(" not in js
    assert "localStorage" not in js
    for path in ("app/templates/vial_labels423.html",
                 "app/templates/vial_label_sheets447.html"):
        html = source(path)
        Environment().parse(html)
        assert 'id="label633MediaSummary"' in html
        assert "actual size" in html
        assert "test strip" in html
        assert "tracker-label-print-guide633.js?v=633" in html
        assert "tracker-label-preview-zoom449.js?v=449" in html


def test_dependency_replay_package_only_skips_full_suites():
    code = source("scripts/tracker_freshenv570.py")
    assert '"--packages-only"' in code
    assert 'FRESHENV_PACKAGES_ONLY=PASSED' in code
    assert code.index("if packages_only:") < code.index("Downloading and launching separate Chromium")
    assert 'if args.packages_only and not args.execute:' in code
    assert 'execute(sha, retain=args.retain_artifacts, packages_only=True)' in code
    assert "FRESHENV_BACKEND_SUITE=PASSED" in code
    assert "FRESHENV_BROWSER_SUITE=PASSED" in code
