"""End-to-end smoke test through the real FastAPI app (needs requirements-dev.txt)."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app, follow_redirects=True) as c:
        yield c


def test_full_flow(client):
    assert client.get("/healthz").json() == {"ok": True}
    for path in ("/", "/compounds", "/purchases", "/vials", "/doses", "/protocols"):
        assert client.get(path).status_code == 200

    client.post("/compounds", data={"name": "Test Peptide", "category": "peptide"})
    client.post("/compounds", data={"name": "Test Cyp", "category": "testosterone"})

    # purchase: two powder vials, $100 each, $20 shipping -> $110 landed each
    r = client.post("/purchases", data={"vendor": "Acme", "shipping": "20"})
    pid = int(re.search(r"/purchases/(\d+)", str(r.url)).group(1))
    client.post(f"/purchases/{pid}/vials", data={
        "compound_id": 1, "form": "lyophilized", "quantity": 2, "content_value": 10,
        "content_unit": "mg", "unit_price": "100", "label": "10 mg"})
    page = client.get(f"/purchases/{pid}").text
    assert "$110.00" in page

    # reconstitute vial 1 with 2 mL -> 5 mg/mL
    client.post("/vials/1/reconstitute", data={"volume_ml": 2})
    assert "5 mg/mL" in client.get("/vials/1").text

    # volume dose of 0.1 mL = 500 mcg ; cost = 500/10000 * $110 = $5.50
    pv = client.post("/doses/preview", data={"vial_id": 1, "amount": "0.1", "unit": "mL"})
    assert "500 mcg" in pv.text and "$5.50" in pv.text
    ok = client.post("/doses", data={"vial_id": 1, "amount": "0.1", "unit": "mL"})
    assert "500 mcg" in ok.text
    bad = client.post("/doses", data={"vial_id": 2, "amount": "0.1", "unit": "mL"})
    assert bad.headers.get("HX-Retarget") == "#form-msg"   # vial 2 has no volume yet

    # COA upload with content mismatch, then opt in to COA content
    pdf = b"%PDF-1.4\n%fake\n"
    r = client.post("/vials/1/coas", files={"file": ("coa.pdf", pdf, "application/pdf")},
                    data={"purity_pct": "99.2", "reported_content": "9", "reported_unit": "mg"})
    assert "COA uploaded" in r.text
    evil = client.post("/vials/1/coas", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert "don&#39;t match" in evil.text or "don't match" in evil.text
    assert client.get("/coas/1/file").content == pdf
    form = {"status": "in_use", "content_value": 10, "content_unit": "mg", "unit_price": "100",
            "volume_ml": 2, "use_coa_content": "on"}
    client.post("/vials/1", data=form)
    assert "from COA" in client.get("/vials/1").text

    # protocol what-if
    r = client.post("/protocols", data={"name": "Plan A"})
    ppid = int(re.search(r"/protocols/(\d+)", str(r.url)).group(1))
    rows = {"compound_id": ["1"], "amount": ["250"], "unit": ["mcg"], "freq_count": ["5"],
            "freq_period": ["week"], "horizon_weeks": "12"}
    calc = client.post(f"/protocols/{ppid}/calc", data=rows)
    assert calc.status_code == 200 and "Cost per month" in calc.text
    assert "Saved" in client.post(f"/protocols/{ppid}/save", data=rows | {"name": "Plan A"}).text
    rows["freq_count"] = ["7"]
    assert "vs saved" in client.post(f"/protocols/{ppid}/calc", data=rows).text


def test_vitals_and_notes(client):
    # vitals: lb entry is stored in kg and shown in the display unit (kg by default)
    client.post("/vitals", data={"weight": "180", "weight_unit": "lb", "systolic": "118",
                                 "diastolic": "76", "pulse": "62", "context": "morning"})
    page = client.get("/vitals").text
    assert "81.6" in page and "118/76" in page and "<svg" in page
    bad = client.post("/vitals", data={"systolic": "70", "diastolic": "120"})
    assert "swapped" in bad.text
    assert "at least one" in client.post("/vitals", data={}).text.lower()
    rid = int(re.search(r"/vitals/(\d+)", page).group(1))
    assert client.delete(f"/vitals/{rid}").headers.get("HX-Refresh") == "true"

    # notes: create two pages, link them, add sources, check safety
    r = client.post("/pages", data={"title": "First note", "tags": "Reading, Sleep",
                                    "body": "# Heading\n\nSee [[Second note]] and <script>alert(1)</script>",
                                    "compound_ids": [1]})
    pid = int(re.search(r"/pages/(\d+)", str(r.url)).group(1))
    client.post("/pages", data={"title": "Second note", "body": "Backlink target"})
    view = client.get(f"/pages/{pid}").text
    assert 'class="wikilink"' in view and "<script>alert" not in view
    assert "Linked from" in client.get("/pages/2").text
    client.post(f"/pages/{pid}/sources", data={"kind": "book", "title": "Some Book", "author": "A. Writer",
                                               "location": "ch. 3"})
    client.post(f"/pages/{pid}/sources", data={"kind": "web", "title": "Article",
                                               "url": "https://example.org/a"})
    bad = client.post(f"/pages/{pid}/sources", data={"title": "x", "url": "javascript:alert(1)"})
    assert "http://" in bad.text
    view = client.get(f"/pages/{pid}").text
    assert "Some Book" in view and 'href="https://example.org/a"' in view
    assert "First note" in client.get("/pages?q=writer").text           # searches sources
    assert "First note" in client.get("/pages?tag=sleep").text
    assert "First note" in client.get("/pages?compound_id=1").text
    assert "already exists" in client.post("/pages", data={"title": "first NOTE"}).text
    prev = client.post("/pages/preview", data={"body": "**hi** [[First note]]"})
    assert "<strong>hi</strong>" in prev.text and f"/pages/{pid}" in prev.text


def test_events_overlay_and_labs(client):
    # --- events on vitals charts (doses were logged "now" in test_full_flow)
    client.post("/vitals", data={"weight": "80", "weight_unit": "kg"})
    page = client.get("/vitals?days=30").text
    assert 'class="tick l0"' in page and "doses <small>(lane 1)</small>" in page
    assert 'class="tick' not in client.get("/vitals?days=30&events=0").text

    # --- lab reports
    pdf = b"%PDF-1.4\n%fake lab report\n"
    r = client.post("/labs", data={
        "drawn_on": "2026-09-01", "lab_name": "Lab A", "analyte": ["Total testosterone", "Glucose"],
        "value": ["600", "90"], "unit": ["ng/dL", "mg/dL"], "ref_low": ["264", ""], "ref_high": ["916", ""]},
        files={"file": ("rep.pdf", pdf, "application/pdf")})
    assert "Saved 2 result" in r.text and "within" in r.text
    client.post("/labs", data={
        "drawn_on": "2026-10-01", "lab_name": "Lab B", "analyte": ["Testosterone"], "value": ["18"],
        "unit": ["nmol/L"], "ref_low": ["9.2"], "ref_high": ["31.8"]})
    assert client.get("/labs/1/file").content == pdf

    index = client.get("/labs").text
    assert "Trends by analyte" in index and "<svg" in index
    detail = client.get("/labs/analyte?name=testosterone").text
    assert "20.8" in detail                       # 600 ng/dL converted into the newest unit (nmol/L)
    assert 'class="tick l0"' in detail            # dose ticks overlaid on the lab chart
    assert 'class="tick' not in client.get("/labs/analyte?name=testosterone&events=0").text

    # validation re-renders the form instead of losing input
    bad = client.post("/labs", data={"drawn_on": "2026-10-02", "analyte": ["Ferritin"], "value": ["50"],
                                     "unit": [""], "ref_low": [""], "ref_high": [""]})
    assert "needs a unit" in bad.text and 'value="Ferritin"' in bad.text
    half = client.post("/labs", data={"drawn_on": "2026-10-02", "analyte": ["Ferritin"], "value": ["50"],
                                      "unit": ["ng/mL"], "ref_low": ["30"], "ref_high": [""]})
    assert "both ends" in half.text
    junk = client.post("/labs", data={"drawn_on": "2026-10-02", "analyte": ["X"], "value": ["1"], "unit": ["u"],
                                      "ref_low": [""], "ref_high": [""]},
                       files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert "match its extension" in junk.text
    assert client.get("/labs/analyte?name=nonexistent").status_code == 404
