"""Release 743 single-release finish: current CSRF inventory, browser/OS evidence,
independent DEV/PROD stage bases, and global CSS computed-style parity.

All tests are offline or use disposable Chromium markup; never touch the live DB,
install packages, contact a host or enable global strict CSRF.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import tracker_security_readiness743 as csrf
from scripts import tracker_browser_provenance743 as browser
from scripts import tracker_stage_chain743 as chain

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "8b44bc133d7a0b1582ee11b2acf87809616fab10"
STYLES = ROOT / "app/static/css"
HTML = ROOT / "app/templates/base.html"


def test_743_current_source_includes_new_macd_and_does_not_enable_global_csrf():
    report = csrf.build()
    assert report["scope"] == "static source declarations only"
    assert report["total_unsafe_declarations"] >= 200
    assert report["historical_candidate_source_witnesses_still_declared"] >= 20
    assert report["routes_outside_frozen_candidate_source_witnesses"] > 0
    assert report["newer_routes_evidence_not_assumed"] is True
    assert report["global_strict_csrf_enforcement_authorized"] is False
    assert report["installed_policy"] == "REPORT_ONLY_UNCHANGED"
    assert {(r["method"], r["path"]) for r in report["unreviewed_recent_macd_routes"]} == csrf.NEW_MACD
    assert csrf.main([]) == 0
    assert csrf.main(["--require-strict-ready"]) == 3


def test_743_security_readiness_rejects_source_default_drift(tmp_path):
    root = tmp_path
    (root / "app").mkdir()
    main = (ROOT / "app/main.py").read_text()
    policy = (ROOT / "app/csrf_policy289.py").read_text()
    (root / "app/main.py").write_text(main.replace(
        'os.environ.get("TRACKER_CSRF_ENFORCE", "0")',
        'os.environ.get("TRACKER_CSRF_ENFORCE", "1")',
    ))
    (root / "app/csrf_policy289.py").write_text(policy)
    with pytest.raises(ValueError, match="Report-only"):
        csrf.build(root)


def test_743_security_route_flatten_is_deterministic_and_source_only():
    first = csrf.route_rows(ROOT)
    second = csrf.route_rows(ROOT)
    assert first == second
    assert all(row["method"] in csrf.UNSAFE and row["file"].startswith("app/") for row in first)
    assert {("POST", "/supplies/{sid}/delete"),
            ("POST", "/workouts/equipment/{equipment_id}/delete")} <= {
                (row["method"], row["path"]) for row in first
            }


def binary_fixture(tmp_path):
    file = tmp_path / "chromium-real-binary"
    file.write_bytes(b"fake-chromium-executable-for-offline-tests-only" * 16)
    file.chmod(0o700)
    return file


def provenance(file):
    return browser.snapshot(
        file, py="3.13.5", playwright="1.64.1",
        operating_system=("ubuntu", "24.04"), libc=("glibc", "2.39"),
    )


def test_743_browser_provenance_matches_exact_approved_python_package_baseline(tmp_path):
    sample = binary_fixture(tmp_path)
    fingerprint = provenance(sample)
    assert browser.validate(fingerprint) == fingerprint
    assert fingerprint["chromium_sha256"] == sha256(sample.read_bytes()).hexdigest()
    comparison = browser.compare(fingerprint, dict(fingerprint))
    assert comparison["fingerprints_equal"] is True
    assert comparison["dev_prod_browser_python_os_identical"] is True
    assert comparison["matching_approved_python_playwright_baseline"] is True
    assert comparison["issue10_closed"] is False
    assert comparison["os_dependency_rollback_tested"] is False


@pytest.mark.parametrize("change", ["binary", "playwright", "os", "python"])
def test_743_browser_provenance_discrepancy_fails_comparison(tmp_path, change):
    sample = binary_fixture(tmp_path)
    dev = provenance(sample)
    prod = dict(dev)
    if change == "binary":
        prod["chromium_sha256"] = "e" * 64
    elif change == "playwright":
        prod["playwright"] = "1.64.2"
    elif change == "os":
        prod["os_version"] = "24.10"
    else:
        prod["python"] = "3.14.0"
    comparison = browser.compare(dev, prod)
    assert comparison["fingerprints_equal"] is False
    assert comparison["issue10_closed"] is False


def test_743_browser_provenance_receipts_are_private_not_git(tmp_path):
    out = tmp_path / "evidence"
    out.mkdir(mode=0o700)
    out.chmod(0o700)
    sample = binary_fixture(tmp_path)
    report = provenance(sample)
    target = out / "dev.json"
    browser.write_private(target, report)
    assert target.stat().st_mode & 0o077 == 0
    assert browser.read_receipt(target) == report
    with pytest.raises(FileExistsError):
        browser.write_private(target, report)
    link = out / "symlink.json"
    link.symlink_to(target)
    with pytest.raises(browser.BrowserEvidenceError):
        browser.read_receipt(link)
    sample.write_bytes(b"replacement bytes")
    assert provenance(sample)["chromium_sha256"] != report["chromium_sha256"]


def test_743_browser_provenance_refuses_unsafe_and_invalid_files(tmp_path):
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    with pytest.raises(browser.BrowserEvidenceError):
        browser.hash_binary(empty)
    link = tmp_path / "link"
    link.symlink_to(empty)
    with pytest.raises(browser.BrowserEvidenceError):
        browser.hash_binary(link)
    bad = provenance(binary_fixture(tmp_path))
    bad["extra_host_path"] = "/home/secret"
    with pytest.raises(browser.BrowserEvidenceError):
        browser.validate(bad)


def receipt(action, n, base, target, release=743, predecessor=None):
    marker = {
        "qualify": f"RELEASE_{release}_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY",
        "dev_install": f"RELEASE_{release}_DEV_INSTALL=SUCCESS",
        "prod_preflight": "PREFLIGHT=PASSED",
        "prod_deploy": "PROD_INSTALLED_COMMIT=" + target,
    }[action]
    return {
        "schema": 1, "action": action, "status": "passed", "exit_code": 0,
        "request_id": f"r743-case-{n}", "release": release,
        "ref": "release/743-security-deps-controller-ux",
        "target": target, "base": base,
        "markers": [marker] + (
            ["DEV_CONTROLLED_RELEASE=SUCCESS"] if action == "prod_deploy" else []
        ),
        "previous_request_id": predecessor,
        "finished_at_utc": (datetime(2026, 11, 21, 15, tzinfo=timezone.utc)
                            + timedelta(minutes=n)).isoformat(),
    }


def fixture_receipts():
    target, dev_base, prod_base = "a" * 40, "b" * 40, "c" * 40
    q = receipt("qualify", 1, dev_base, target)
    d = receipt("dev_install", 2, dev_base, target, predecessor=q["request_id"])
    p = receipt("prod_preflight", 3, prod_base, target, predecessor=d["request_id"])
    deployed = receipt("prod_deploy", 4, prod_base, target, predecessor=p["request_id"])
    return target, dev_base, prod_base, dict(zip(chain.STAGES, (q, d, p, deployed)))


def verify(receipts, prod_base, target, main, ancestor=lambda _root, _base, _target: True):
    return chain.verify(
        receipts, release=743, ref="release/743-security-deps-controller-ux",
        target=target, prod_base=prod_base, main=main,
        ancestor=ancestor, git_root=ROOT,
    )


def test_743_cumulative_dev_ahead_of_prod_is_allowed_when_both_bases_have_ancestry():
    target, dev_base, prod_base, receipts = fixture_receipts()
    observed = []
    def ancestor(_root, base, final):
        observed.append((base, final))
        return True
    outcome = verify(receipts, prod_base, target, main=target, ancestor=ancestor)
    assert outcome["chain"] == "PASS"
    assert outcome["dev_base_differs_from_prod"] is True
    assert observed == [(dev_base, target), (prod_base, target)]
    assert outcome["external_approval_and_host_checks_still_required"] is True
    # Read-only preflight may be run while main still points at PROD base.
    partial = dict(list(receipts.items())[:3])
    assert verify(partial, prod_base, target, main=prod_base)["chain"] == "PASS"


@pytest.mark.parametrize("tamper", [
    "wrong-qual-target", "wrong-install-base", "wrong-prod-base",
    "wrong-prev", "duplicate-id", "stale-stage-time", "wrong-marker",
    "failed-status", "missing-preflight", "wrong-main", "not-ancestor",
])
def test_743_stage_chain_rejects_tampering_and_accumulated_stage_drift(tamper):
    target, dev_base, prod_base, receipts = fixture_receipts()
    main = target
    ancestor = lambda _root, _base, _target: True
    if tamper == "wrong-qual-target":
        receipts["qualify"]["target"] = "e" * 40
    elif tamper == "wrong-install-base":
        receipts["dev_install"]["base"] = "f" * 40
    elif tamper == "wrong-prod-base":
        receipts["prod_preflight"]["base"] = dev_base
    elif tamper == "wrong-prev":
        receipts["prod_deploy"]["previous_request_id"] = "missing"
    elif tamper == "duplicate-id":
        receipts["prod_deploy"]["request_id"] = receipts["prod_preflight"]["request_id"]
    elif tamper == "stale-stage-time":
        receipts["dev_install"]["finished_at_utc"] = "2026-11-20T12:00:00+00:00"
    elif tamper == "wrong-marker":
        receipts["prod_deploy"]["markers"] = ["PREFLIGHT=PASSED"]
    elif tamper == "failed-status":
        receipts["qualify"]["status"] = "failed"
    elif tamper == "missing-preflight":
        del receipts["prod_preflight"]
    elif tamper == "wrong-main":
        main = "1" * 40
    elif tamper == "not-ancestor":
        ancestor = lambda _root, base, _target: base != prod_base
    with pytest.raises(chain.StageChainError):
        verify(receipts, prod_base, target, main=main, ancestor=ancestor)


def test_743_immutable_receipts_refuse_symlink_and_missing_outcome(tmp_path):
    _target, _, _, receipts = fixture_receipts()
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipts["qualify"]))
    assert chain.parse_receipt(path)["action"] == "qualify"
    linked = tmp_path / "linked.json"
    linked.symlink_to(path)
    with pytest.raises(chain.StageChainError):
        chain.parse_receipt(linked)
    path.write_text(json.dumps({**receipts["qualify"], "status": "blocked"}))
    with pytest.raises(chain.StageChainError):
        chain.parse_receipt(path)


def test_743_shared_css_combines_original_two_layers_in_exact_order():
    original_foundation = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT),
         "show", f"{BASE_SHA}:app/static/css/tracker-ui-foundation679.css"],
        text=True,
    )
    shortcut = (STYLES / "tracker-shortcut-buttons676.css").read_text()
    merged = (STYLES / "tracker-ui-foundation679.css").read_text()
    delimiter = "/* Release 743: unchanged shortcut tile rules consolidated"
    assert merged.startswith(original_foundation.rstrip() + "\n\n" + delimiter)
    assert merged.endswith(shortcut.rstrip() + "\n")
    base = HTML.read_text()
    assert base.count("tracker-ui-foundation679.css?v=743") == 1
    assert "tracker-shortcut-buttons676.css?v=676" not in base
    assert base.index("tracker-mobile-ux673.css?v=673") < base.index(
        "tracker-ui-foundation679.css?v=743"
    ) < base.index("tracker-explanation-touch680.css?v=680")
    # No rewrite of the deliberate content-sized Rapid Gym later override.
    assert base.index("tracker-ui-foundation679.css?v=743") < base.index(
        "tracker-workout-nav-density681.css?v=681"
    )


@pytest.mark.parametrize("width", [320, 390, 430, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_743_consolidated_css_computed_accessibility_contract(width, scheme):
    """Byte-for-byte source parity is proven above. Validate rendered UX here.

    A comparison that replaces a live stylesheet in one page can capture an
    in-flight CSS color transition. Use a fresh DOM and the final unchanged
    rules to check real browser layout, focus and touch targets instead.
    """
    from playwright.sync_api import sync_playwright
    merged = (STYLES / "tracker-ui-foundation679.css").read_text()
    downstream = (STYLES / "tracker-workout-nav-density681.css").read_text()
    markup = """<!doctype html><html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>:root{--surface:#ffffff;--ink:#172b39;--rule:#a9bacb;
    --teal:#1265ad;--teal-ink:#ffffff;--wash:#edf3f9}
    *{box-sizing:border-box} body{margin:0;padding:12px;font:16px sans-serif}
    </style></head><body><main id="main-content">
    <nav class="tracker-ui-actions"><a class="tracker-ui-action tracker-ui-action--primary"
      href="#a">Record set</a><button class="tracker-ui-action">Edit</button></nav>
    <section class="tracker-ui-card"><div class="tracker-ui-card__value">12</div></section>
    <nav class="ux675-actions ux675-gym-top"><a href="#workouts">Workouts</a>
    <a href="#progress">Progress</a><details class="ux675-more">
    <summary>More</summary><div><a href="#history">History</a></div></details></nav>
    <a href="#machine" class="ux675-inline-action">Machine history</a>
    </main></body></html>"""
    with sync_playwright() as pw:
        browser_instance = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser_instance.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(markup)
            page.add_style_tag(content=merged + "\n" + downstream)
            assert page.locator(".tracker-ui-action").count() == 2, "CSS743_COUNT"
            primary = page.locator(".tracker-ui-action--primary")
            assert primary.evaluate(
                "e => getComputedStyle(e).display === 'inline-flex'"
            ), "CSS743_PRIMARY_DISPLAY"
            assert primary.evaluate(
                "e => e.getBoundingClientRect().height >= 44"
            ), "CSS743_PRIMARY_HEIGHT"
            nav = page.locator(".ux675-gym-top")
            assert nav.evaluate(
                "e => getComputedStyle(e).display === 'flex'"
            ), "CSS743_GYM_NAV_DISPLAY"
            for selector in (
                ".ux675-gym-top > a",
                ".ux675-more > summary",
                ".ux675-inline-action",
            ):
                targets = page.locator(selector)
                assert targets.count() >= 1, "CSS743_TARGET_COUNT"
                assert targets.evaluate_all(
                    "els => els.every(e => e.getBoundingClientRect().height >= 44)"
                ), "CSS743_TARGET_HEIGHT"
            # :focus-visible is a keyboard modality contract; clicking a
            # different control first switches Chromium to pointer modality.
            page.keyboard.press("Tab")
            assert primary.evaluate(
                "e => document.activeElement === e && getComputedStyle(e).outlineStyle === 'solid'"
            ), "CSS743_KEYBOARD_FOCUS"
            page.locator(".ux675-more > summary").click()
            assert page.locator(".ux675-more").evaluate("e => e.open"), "CSS743_MENU_OPEN"
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), "CSS743_OVERFLOW"
        finally:
            browser_instance.close()
