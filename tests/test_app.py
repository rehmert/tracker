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
