"""Release 748: Notes history touch actions, signed MACD Notes/Labs HTTP."""
from __future__ import annotations
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient
from app import config
from app.csrf_runtime import COOKIE_NAME
from app.main import app

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def isolated748(monkeypatch,tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE","1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD","1")
    monkeypatch.setattr(config,"AUTH_USER","")
    monkeypatch.setattr(config,"AUTH_PASS","")
    monkeypatch.setattr(config,"DATA_DIR",tmp_path)
    yield

def signed(client,url,details):
    token=client.cookies.get(COOKIE_NAME)
    assert token and token.startswith("v1.")
    return client.post(url,data={**details,"csrf_token":token},follow_redirects=False)


@pytest.mark.parametrize("scheme",("http","https"))
def test_748_notes_history_signed_restore_and_small_link_regression(isolated748,scheme):
    with TestClient(app,base_url=f"{scheme}://testserver") as client:
        assert client.get("/pages/new").status_code==200
        values={"title":"748 notes history "+scheme,"body":"original 748","tags":"qa"}
        created=signed(client,"/pages",values)
        assert created.status_code==303
        match=re.search(r"/pages/(\d+)",created.headers["location"])
        assert match
        route=f"/pages/{match.group(1)}"
        updated=signed(client,route,{**values,"body":"edited 748"})
        assert updated.status_code==303
        history=client.get(route+"/history")
        assert history.status_code==200
        assert 'aria-label="Note history actions"' in history.text
        assert history.text.count('class="tracker-macd741-action"') >= 2
        assert 'href="/static/css/tracker-integrated-macd741.css?v=741"' in history.text
        assert "original 748" in history.text
        match=re.search(r'action="/pages/\d+/restore/(\d+)"',history.text)
        assert match
        restore=f"{route}/restore/{match.group(1)}"
        assert client.post(restore,follow_redirects=False).status_code==403
        assert client.post(restore,data={"csrf_token":"forged-748"},follow_redirects=False).status_code==403
        assert "edited 748" in client.get(route).text
        saved=signed(client,restore,{})
        assert saved.status_code==303
        assert "original 748" in client.get(route).text
        assert "edited 748" in client.get(route+"/history").text


@pytest.mark.parametrize("scheme",("http","https"))
def test_748_labs_signed_report_result_edit_delete_and_date_move(isolated748,scheme):
    with TestClient(app,base_url=f"{scheme}://testserver") as client:
        assert client.get("/labs/new").status_code==200
        label="748 synthetic lab "+scheme
        new={"drawn_on":"2026-11-10","lab_name":label}
        assert client.post("/labs",data=new,follow_redirects=False).status_code==403
        created=signed(client,"/labs",new)
        assert created.status_code==303
        match=re.search(r"/labs/(\d+)",created.headers["location"])
        assert match,created.headers["location"]
        route=f"/labs/{match.group(1)}"
        assert label in client.get(route).text

        result={"analyte":"748 QA Analyte","value":"90","unit":"mg/dL"}
        assert client.post(route+"/results",data={**result,"csrf_token":"fake"},
                           follow_redirects=False).status_code==403
        added=signed(client,route+"/results",result)
        assert added.status_code==303
        html=client.get(route).text
        found=re.search(r'action="/lab-results/(\d+)/edit"',html)
        assert found, "Signed positive analyte was not persisted"
        xid=found.group(1)
        replaced=signed(client,f"/lab-results/{xid}/edit",
                        {**result,"value":"95"})
        assert replaced.status_code==303
        assert "95" in client.get(route).text
        changed=signed(client,route+"/edit",{
            "drawn_on":"2026-11-11","lab_name":label+" corrected","notes":"QA"
        })
        assert changed.status_code==303
        assert label+" corrected" in client.get(route).text
        assert client.post(f"/lab-results/{xid}/delete",follow_redirects=False).status_code==403
        removed=signed(client,f"/lab-results/{xid}/delete",{})
        assert removed.status_code==303
        assert f'action="/lab-results/{xid}/edit"' not in client.get(route).text
        assert signed(client,route+"/delete",{}).status_code==303
        assert client.get(route).status_code==404


def test_748_notes_history_actual_template_has_form_and_scoped_actions():
    source=(ROOT/"app/templates/page_history.html").read_text()
    assert '<nav class="tracker-macd741-actions" aria-label="Note history actions">' in source
    assert source.count('class="tracker-macd741-action"')==2
    assert 'method="post"' in source and 'Restore this version' in source
    assert 'return confirm(' in source
    assert "Back to note</a>" in source and "Edit current note</a>" in source


def test_748_notes_history_real_css_in_phone_and_keyboard():
    from jinja2 import DictLoader, Environment
    from types import SimpleNamespace
    from playwright.sync_api import sync_playwright
    template=(ROOT/"app/templates/page_history.html").read_text()
    css=(ROOT/"app/static/css/tracker-integrated-macd741.css").read_text()
    shell="<html><head><meta name='viewport' content='width=device-width,initial-scale=1'></head><body>{% block content %}{% endblock %}</body></html>"
    html=Environment(loader=DictLoader({"base.html":shell,"page_history.html":template}),
                     autoescape=True).get_template("page_history.html").render(
                     p=SimpleNamespace(id=21,title="748 synthetic note"),
                     revisions=[SimpleNamespace(id=9,created_at="2026-11-21",title="Before",tags="qa",body="first note")])
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for width in (320,390,430,760,1024):
                for theme in ("light","dark"):
                    page=browser.new_page(viewport={"width":width,"height":800},
                                          color_scheme=theme)
                    page.route("**/*",lambda route:route.abort())
                    page.set_content(html)
                    page.add_style_tag(content=css)
                    nav=page.locator('nav[aria-label="Note history actions"]')
                    assert nav.count()==1
                    controls=nav.locator("a")
                    assert controls.count()==2
                    for link in controls.all():
                        rect=link.bounding_box()
                        assert rect and rect["height"]>=44 and rect["width"]>=44
                        assert rect["x"]>=-1 and rect["x"]+rect["width"]<=width+1
                        link.focus()
                        assert link.evaluate("(el)=>document.activeElement===el")
                    summary=page.locator("details summary")
                    assert summary.count()==1
                    summary.click()
                    assert page.locator('form[action="/pages/21/restore/9"] button').is_visible()
                    page.close()
        finally:
            browser.close()
