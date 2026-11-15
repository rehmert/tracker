"""Release 636: focused inline catalog lookup source and isolated HTTP tests.

No live internet, data migration, or real Tracker database access.
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment

from app.routers import regimen_catalog636 as catalog

pytestmark = pytest.mark.quick
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def empty_cache():
    with catalog._LOCK:
        catalog._CACHE.clear()
    yield
    with catalog._LOCK:
        catalog._CACHE.clear()


def test_rxnorm_results_are_bounded_and_normalized(monkeypatch):
    def fake(url, params):
        assert url == catalog._RX
        assert params == {"name": "testosterone"}
        return {"drugGroup": {"conceptGroup": [
            {"conceptProperties": [
                {"rxcui": "123", "name": "Testosterone Cypionate Injection"},
                {"rxcui": "124", "name": "Testosterone Injection"},
            ]}
        ]}}
    monkeypatch.setattr(catalog, "_fetch", fake)
    values = catalog._rxnorm("testosterone")
    assert len(values) == 2
    assert values[0]["source"] == "RxNorm"
    assert values[0]["source_id"] == "123"
    assert values[0]["name"] == "Testosterone Cypionate Injection"
    assert values[0]["strength"] == ""  # Never invent labeled strength.


def test_openfda_ndc_product_fields_and_safe_term(monkeypatch):
    def fake(url, params):
        assert url == catalog._FDA
        assert " OR " in params["search"]
        assert "danger:exploit" not in params["search"]
        return {"results": [{
            "product_ndc": "12345-678",
            "brand_name": "Test Product",
            "generic_name": "testosterone cypionate",
            "dosage_form": "INJECTION, SOLUTION",
            "active_ingredients": [
                {"name": "TESTOSTERONE CYPIONATE", "strength": "200 mg/mL"}
            ],
        }]}
    monkeypatch.setattr(catalog, "_fetch", fake)
    results = catalog._openfda("testosterone danger:exploit")
    assert results[0]["source_id"] == "12345-678"
    assert results[0]["strength"] == "200 mg/mL"
    assert results[0]["ingredient"] == "TESTOSTERONE CYPIONATE"
    assert results[0]["form"] == "INJECTION, SOLUTION"


def test_dsld_product_label_does_not_infer_multingredient_strength(monkeypatch):
    def fake(url, params):
        assert url == catalog._DSLD
        assert params["method"] == "by_keyword"
        assert params["size"] == 8
        return {"hits": [{"_id": "82118", "_source": {
            "fullName": "Nutrient 950", "brandName": "Example Brand"
        }}]}
    monkeypatch.setattr(catalog, "_fetch", fake)
    results = catalog._dsld("Nutrient 950")
    assert results == [{
        "source": "NIH DSLD", "source_id": "82118",
        "name": "Nutrient 950", "ingredient": "", "strength": "",
        "form": "", "brand": "Example Brand"
    }]


def test_provider_failure_fails_open_to_manual_entry_not_saved(monkeypatch):
    def bad(_):
        raise TimeoutError("provider timeout")
    monkeypatch.setattr(catalog, "_rxnorm", bad)
    monkeypatch.setattr(catalog, "_openfda", bad)
    result = catalog.suggestions("medication", "testosterone")
    assert result["results"] == []
    assert result["unavailable"] == ["rxnorm", "openfda"]
    assert ("medication", "testosterone") not in catalog._CACHE


def test_partial_provider_failure_keeps_good_results(monkeypatch):
    monkeypatch.setattr(catalog, "_rxnorm", lambda _: [{
        "source": "RxNorm", "source_id": "222", "name": "Drug X",
        "ingredient": "", "strength": "", "form": "", "brand": ""
    }])
    monkeypatch.setattr(catalog, "_openfda", lambda _: (_ for _ in ()).throw(TimeoutError()))
    response = catalog.suggestions("medication", "Drug X")
    assert len(response["results"]) == 1
    assert response["unavailable"] == ["openfda"]


def test_suggest_http_input_validation_and_success(monkeypatch):
    app = FastAPI()
    app.include_router(catalog.router)
    monkeypatch.setattr(catalog, "suggestions", lambda kind, q: {
        "results": [{"name": q, "source": "NIH DSLD", "source_id": "9"}],
        "unavailable": []
    })
    with TestClient(app) as client:
        assert client.get("/regimen/catalog/suggest", params={"kind": "invalid", "q": "foo"}).status_code == 422
        assert client.get("/regimen/catalog/suggest", params={"kind": "supplement", "q": "x"}).status_code == 422
        assert client.get("/regimen/catalog/suggest", params={"kind": "supplement", "q": "x" * 81}).status_code == 422
        valid = client.get("/regimen/catalog/suggest", params={"kind": "supplement", "q": "Vitamin D"})
        assert valid.status_code == 200
        assert valid.json()["results"][0]["name"] == "Vitamin D"


def test_no_new_workflow_and_original_forms_are_intact():
    html = (ROOT / "app/templates/regimen635.html").read_text()
    script = (ROOT / "app/static/js/tracker-regimen-catalog636.js").read_text()
    Environment().parse(html)
    assert html.count('data-reg636-catalog>') == 2
    assert 'action="/regimen/items"' in html
    assert 'action="/regimen/items/{{ item.id }}/edit"' in html
    assert html.count('data-reg636-results role="listbox"') == 2
    assert html.count('data-reg636-status') == 2
    assert 'tracker-regimen-catalog636.js?v=636' in html
    assert "new URLSearchParams({kind: kind.value, q})" in script
    assert "method: 'GET'" in script
    assert "option.type = 'button'" in script
    assert "form.requestSubmit" not in script
    assert "form.submit" not in script
    assert "submit', " not in script
    assert "textContent = match.name" in script
    assert "Catalog reference: " in script
    assert "['name', 'ingredient', 'strength', 'form']" in script
    assert "['amount', 'schedule', 'instructions']" not in script


def test_dsld_label_details_multi_ingredient_and_labeled_serving(monkeypatch):
    def fake(url, params):
        assert url.endswith("/api/v9/label/82118")
        assert params == {}
        return {
            "ingredientRows": [
                {"name": "Vitamin C", "quantity": [{"quantity": 100, "unit": "mg"}]},
                {"name": "Magnesium", "quantity": [{"quantity": 25, "unit": "mg"}]},
            ],
            "servingSizes": [{"minQuantity": 2, "unit": "Capsules"}],
            "physicalState": {"langualCodeDescription": "Capsule"},
        }
    monkeypatch.setattr(catalog, "_fetch", fake)
    data = catalog.supplement_label("82118")
    assert data == {
        "available": True, "ingredients": "Vitamin C 100 mg; Magnesium 25 mg",
        "form": "Capsule", "serving": "2 Capsules",
    }


def test_dsld_label_id_is_validated_before_network(monkeypatch):
    monkeypatch.setattr(catalog, "_fetch", lambda *_: (_ for _ in ()).throw(
        AssertionError("Invalid identifier must not reach provider")))
    with pytest.raises(Exception) as exc:
        catalog.supplement_label("../private")
    assert getattr(exc.value, "status_code", None) == 422


def test_dsld_detail_failures_never_block_manual_entry(monkeypatch):
    monkeypatch.setattr(catalog, "_fetch", lambda *_: (_ for _ in ()).throw(
        TimeoutError("network timeout")))
    assert catalog.supplement_label("82118") == {
        "available": False, "ingredients": "", "form": "", "serving": "",
    }
