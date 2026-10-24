import importlib

import pytest
from fastapi.testclient import TestClient

from webapp import model_service


class StubService:
    demo_mode = False
    data_provenance = "real"

    def predict(self, **values):
        return values

    def model_info(self):
        return {"demo_mode": self.demo_mode, "data_provenance": self.data_provenance}


@pytest.fixture
def client(monkeypatch):
    service = StubService()
    monkeypatch.setattr(model_service, "ModelService", lambda: service)
    main = importlib.import_module("webapp.main")
    monkeypatch.setattr(main, "service", service)
    with TestClient(main.app) as client:
        yield client


def request_body(**changes):
    body = {"allele_freq_afr": 0.01, "cadd_score": 25, "gene_region": "exonic",
            "conservation_phylop": 1, "gene_name": "HBB"}
    body.update(changes)
    return body


@pytest.mark.parametrize("changes", [
    {"gene_name": "unknown"}, {"gene_region": "unknown"},
    {"allele_freq_afr": -0.1}, {"cadd_score": 61},
])
def test_invalid_prediction_input_is_rejected(client, changes):
    assert client.post("/api/predict", json=request_body(**changes)).status_code == 422


def test_prediction_normalizes_valid_gene_and_region(client):
    response = client.post("/api/predict", json=request_body(gene_name=" hbb ", gene_region=" EXONIC "))
    assert response.status_code == 200
    assert response.json()["gene_name"] == "HBB"
    assert response.json()["gene_region"] == "exonic"


def test_health_reports_loaded_model_state(client):
    assert client.get("/api/health").json() == {
        "status": "ok", "demo_mode": False, "data_provenance": "real",
    }


def test_unknown_gene_heatmap_is_not_served(client):
    assert client.get("/api/heatmap/unknown").status_code == 404
