"""Release 730: rich medication matches must survive RxNorm's eight-slot cap."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import regimen_catalog636 as catalog

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    with catalog._LOCK:
        catalog._CACHE.clear()
    yield
    with catalog._LOCK:
        catalog._CACHE.clear()


def name_only_rxnorm():
    return [
        {"source": "RxNorm", "source_id": str(i),
         "name": f"Medication concept {i}", "ingredient": "",
         "strength": "", "form": "", "brand": ""}
        for i in range(8)
    ]


def rich_openfda():
    return {
        "source": "openFDA", "source_id": "12345-678",
        "name": "Sample 10 mg tablet", "ingredient": "sample ingredient",
        "strength": "10 mg", "form": "TABLET", "brand": "Sample",
    }


def test_730_eight_rxnorm_names_cannot_hide_structured_fda_details(monkeypatch):
    calls = []
    monkeypatch.setattr(catalog, "_rxnorm", lambda term: (
        calls.append(("rxnorm", term)) or name_only_rxnorm()
    ))
    monkeypatch.setattr(catalog, "_openfda", lambda term: (
        calls.append(("openfda", term)) or [rich_openfda()]
    ))
    result = catalog.suggestions("medication", "sample")
    assert calls == [("rxnorm", "sample"), ("openfda", "sample")]
    assert len(result["results"]) == catalog._MAX_RESULTS
    assert result["results"][0] == rich_openfda()
    assert result["unavailable"] == []
    assert result["results"][1]["source"] == "RxNorm"
    # No second network request for the same cached query.
    assert catalog.suggestions("medication", "sample") == result
    assert len(calls) == 2


def test_730_provider_outage_remains_manual_and_name_only(monkeypatch):
    monkeypatch.setattr(catalog, "_rxnorm", lambda _: name_only_rxnorm())
    monkeypatch.setattr(
        catalog, "_openfda", lambda _: (_ for _ in ()).throw(TimeoutError()),
    )
    result = catalog.suggestions("medication", "sample")
    assert len(result["results"]) == 8
    assert result["unavailable"] == ["openfda"]
    assert all(not entry["strength"] for entry in result["results"])
    assert all(not entry["ingredient"] for entry in result["results"])


def test_730_supplements_are_not_reordered_and_fda_fields_are_bounded(monkeypatch):
    supplements = [
        {"source": "NIH DSLD", "source_id": "1", "name": "First", "brand": ""},
        {"source": "NIH DSLD", "source_id": "2", "name": "Second", "brand": ""},
    ]
    monkeypatch.setattr(catalog, "_dsld", lambda _: supplements)
    assert catalog.suggestions("supplement", "vitamin")["results"] == supplements

    def fake(url, params):
        assert url == catalog._FDA
        return {"results": [{
            "product_ndc": "12345-678",
            "brand_name": "Sample",
            "generic_name": "sample ingredient",
            "dosage_form": "TABLET",
            "active_ingredients": [{"name": "sample ingredient",
                                    "strength": "10 mg"}],
        }]}
    monkeypatch.setattr(catalog, "_fetch", fake)
    item = catalog._openfda("sample")[0]
    assert item["ingredient"] == "sample ingredient"
    assert item["strength"] == "10 mg"
    assert item["form"] == "TABLET"


def test_730_suggest_endpoint_exposes_prefill_fields(monkeypatch):
    monkeypatch.setattr(catalog, "_rxnorm", lambda _: name_only_rxnorm())
    monkeypatch.setattr(catalog, "_openfda", lambda _: [rich_openfda()])
    app = FastAPI()
    app.include_router(catalog.router)
    with TestClient(app) as client:
        response = client.get("/regimen/catalog/suggest",
                              params={"kind": "medication", "q": "sample"})
        assert response.status_code == 200
        assert response.json()["results"][0]["strength"] == "10 mg"
        assert response.json()["results"][0]["ingredient"] == "sample ingredient"


def test_730_existing_regimen_native_submit_contract_preserved():
    page = (ROOT / "app/templates/regimen635.html").read_text()
    script = (ROOT / "app/static/js/tracker-regimen-catalog636.js").read_text()
    assert page.count('data-reg636-catalog>') == 2
    assert page.count('tracker-regimen-catalog636.js?v=730') == 1
    for name in ("name", "ingredient", "strength", "form"):
        assert page.count('name="' + name + '"') >= 2
    assert 'action="/regimen/items"' in page
    assert 'action="/regimen/items/{{ item.id }}/edit"' in page
    assert "form.requestSubmit" not in script
    assert "form.submit" not in script
    assert "This catalog result has no structured ingredient" in script
