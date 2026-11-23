"""Release 746: sanitized browser/OS evidence, strict mode, and MACD gates."""
from pathlib import Path
import json

import pytest
from jinja2 import Environment
from scripts import tracker_host_evidence746 as ev
from scripts import tracker_security_readiness743 as security
from scripts import tracker_dependency_baseline569 as baseline

ROOT=Path(__file__).resolve().parents[1]


def evidence(tmp_path):
    lib=tmp_path/"libsafe.so"
    lib.write_bytes(b"vetted fixed test library bytes")
    vals=ev.libraries_snapshot([lib])
    base=baseline.read_manifest(baseline.BASELINE)
    return {
      "schema":1,
      "python":base["python"],
      "playwright":base["packages"]["playwright"],
      "os_id":"ubuntu","os_version":"24.04",
      "libc_name":"glibc","libc_version":"2.39",
      "chromium_sha256":"a"*64,"chromium_bytes":12345,
      "libraries":vals,
      "scope":"explicit library list only; no rollback or transitive completeness",
    }


def test_746_host_library_hashes_and_sanitized_comparison(tmp_path):
    a=evidence(tmp_path)
    assert ev.validate(a)==a
    assert not any("/" in key for key in a["libraries"])
    assert ev.compare(a,dict(a))["host_evidence_matches"]
    assert not ev.compare(a,dict(a))["dependency_update_authorized"]
    b=json.loads(json.dumps(a))
    b["libraries"]["libsafe.so"]["sha256"]="b"*64
    assert not ev.compare(a,b)["host_evidence_matches"]


@pytest.mark.parametrize("mutation",[
  lambda x:x.update(path="/etc/shadow"),
  lambda x:x["libraries"].clear(),
  lambda x:x.update(chromium_sha256="bad"),
  lambda x:x["libraries"]["libsafe.so"].update(bytes=0),
  lambda x:x.update(scope="certified"),
  lambda x:x.update(playwright="9.9.9"),
])
def test_746_tampered_or_overclaimed_os_evidence_refused(tmp_path,mutation):
    record=evidence(tmp_path)
    mutation(record)
    with pytest.raises(ev.EvidenceError):
        ev.validate(record)


def test_746_private_evidence_no_clobber_and_no_path_disclosure(tmp_path):
    report=evidence(tmp_path)
    folder=tmp_path/"private"
    folder.mkdir(mode=0o700)
    dest=folder/"dev.json"
    ev.private_write(dest,report)
    assert ev.private_read(dest)==report
    assert dest.stat().st_mode&0o077==0
    assert "/tmp" not in dest.read_text() and "/home" not in dest.read_text()
    with pytest.raises(FileExistsError):
        ev.private_write(dest,report)
    link=folder/"link.json"
    link.symlink_to(dest)
    with pytest.raises(ev.EvidenceError):
        ev.private_read(link)


def test_746_existing_python_pins_not_overwritten():
    installed=baseline.read_manifest(baseline.BASELINE)
    locks=baseline.read_constraints(baseline.CONSTRAINTS)
    baseline.validate_constraints(installed,locks)
    assert len(installed["packages"])==44
    assert len(locks)==43
    assert installed["packages"]["fastapi"]=="0.162.0"
    assert "pip" not in locks


def test_746_latest_water_and_macd_routes_in_unqualified_security_audit():
    report=security.build(ROOT)
    declared={(r["method"],r["path"]) for r in security.route_rows(ROOT)}
    for route in (
        ("POST","/food/water/{entry_id}/edit"),
        ("POST","/regimen/items/{item_id}/delete-supplement"),
        ("POST","/regimen/schedules/{schedule_id}/delete"),
        ("POST","/workouts/routines/{routine_id}/delete"),
        ("POST","/supplies/{sid}/delete"),
    ):
        assert route in declared
    assert report["global_strict_csrf_enforcement_authorized"] is False
    assert report["installed_policy"]=="REPORT_ONLY_UNCHANGED"
    assert report["routes_outside_frozen_candidate_source_witnesses"]>0
    assert security.main(["--require-strict-ready"])==3


@pytest.mark.parametrize("template,required",[
 ("regimen635.html",('Delete supplement','Delete schedule','Edit intake')),
 ("food.html",('Save correction','Delete Template','Edit Saved Food')),
 ("workouts654.html",('Delete equipment','Save Correction','Finish &amp; Review')),
 ("workout_routine_detail655.html",('Edit routine','Delete routine','Add to Routine')),
 ("pages.html",('Edit note','Delete note')),
 ("labs.html",('Edit report','Add a lab report')),
 ("supplies.html",('tracker-macd741-action','Save')),
 ("coas.html",('tracker-coa753-actions','Edit')),
])
def test_746_existing_macd_form_surface_verified_without_fake_actions(template,required):
    text=(ROOT/"app/templates"/template).read_text()
    Environment().parse(text)
    for label in required:
        assert label in text, (template,label)


def test_746_gym_and_global_css_boundaries():
    global_bundle=(ROOT/"app/static/css/tracker-global-density-bundle746.css").read_text()
    parts=("tracker-layout-density685.css","tracker-compact-aggressive686.css",
           "tracker-shortcuts-toolbar687.css","tracker-dashboard-polish688.css",
           "tracker-workout-footnote689.css")
    assert global_bundle=="".join(
        (ROOT/"app/static/css"/name).read_text().rstrip()+"\n"
        for name in parts
    )
    base=(ROOT/"app/templates/base.html").read_text()
    assert base.count("tracker-global-density-bundle746.css?v=746")==1
    for name in parts:
        assert name not in base
    assert base.index("tracker-workout-nav-density681.css?v=681")<base.index(
        "tracker-global-density-bundle746.css?v=746")


@pytest.mark.parametrize("width",(320,390,430,760,1024))
@pytest.mark.parametrize("density",("compact","balanced","comfortable"))
@pytest.mark.parametrize("theme",("light","dark"))
def test_746_global_css_parity_in_browser(width,density,theme):
    from playwright.sync_api import sync_playwright
    root=ROOT/"app/static/css"
    sources=("tracker-layout-density685.css","tracker-compact-aggressive686.css",
             "tracker-shortcuts-toolbar687.css","tracker-dashboard-polish688.css",
             "tracker-workout-footnote689.css")
    old="".join((root/name).read_text().rstrip()+"\n" for name in sources)
    new=(root/"tracker-global-density-bundle746.css").read_text()
    markup=('<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<style id="rules"></style><main id="main-content">'
      '<div class="workspace-toolbar"><a class="tracker-account-action687" href="#">Account</a>'
      '<button id="ux-add-toggle">Add</button></div>'
      '<section class="dashboard-hero"><h1>Overview</h1><p>Activity</p></section>'
      '<div id="tracker-workout-dashboard661"><p class="tracker-workout-footnote661">Workouts</p>'
      '</div><div class="tracker-daily-list"><a href="#">Daily</a></div>'
      '</main>')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":width,"height":844},color_scheme=theme)
            page.set_content(markup)
            page.evaluate("(d)=>document.documentElement.dataset.density=d",density)
            def computed(css):
                page.locator("#rules").evaluate("(el,val)=>el.textContent=val",css)
                return page.evaluate("""()=>({
                   props:['.workspace-toolbar','.tracker-account-action687',
                          '#ux-add-toggle','.dashboard-hero','.tracker-workout-footnote661']
                     .map(selector=>{
                       const st=getComputedStyle(document.querySelector(selector));
                       return [st.display,st.padding,st.margin,st.minHeight,st.fontSize,st.gap];
                     }),
                   fits:document.documentElement.scrollWidth<=innerWidth+1
                })""")
            first=computed(old)
            assert computed(new)==first
            assert first["fits"]
        finally:
            browser.close()
