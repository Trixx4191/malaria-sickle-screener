import json
import warnings

import numpy as np
import pytest

from webapp import model_service


class ProbabilityModel:
    n_jobs = -1
    classes_ = np.array([0, 1])

    def predict_proba(self, X):
        self.received = X.copy()
        return np.array([[0.2, 0.8]])


class OffsetScaler:
    def transform(self, X):
        return X + 10


def bundle(model=None, provenance="real", scaler=None):
    return {
        "model": model or ProbabilityModel(),
        "scaler": scaler,
        "feature_names": model_service.FEATURE_ORDER,
        "data_provenance": provenance,
        "meta": {"auc_all": 0.9},
    }


def test_prediction_applies_saved_scaler_and_limits_parallelism(monkeypatch):
    model = ProbabilityModel()
    monkeypatch.setattr(model_service, "_load_real_bundle", lambda: bundle(model, scaler=OffsetScaler()))
    monkeypatch.delenv("REQUIRE_REAL_MODEL", raising=False)
    monkeypatch.delenv("MODEL_N_JOBS", raising=False)
    service = model_service.ModelService()

    result = service.predict(0.01, 25, "exonic", 1, "HBB")

    np.testing.assert_allclose(model.received, [[10.01, 35, 12, 11, 11, 11]])
    assert result["probability"] == 80
    assert result["contribution_method"] == "heuristic"
    assert model.n_jobs == 1


@pytest.mark.parametrize("artifact", [None, bundle(provenance="synthetic_placeholder")])
def test_production_refuses_missing_or_placeholder_models(monkeypatch, artifact):
    monkeypatch.setenv("REQUIRE_REAL_MODEL", "true")
    monkeypatch.setattr(model_service, "_load_real_bundle", lambda: artifact)
    monkeypatch.setattr(model_service, "_train_synthetic_fallback", lambda: pytest.fail("Production trained a fallback"))
    with pytest.raises(RuntimeError, match="REQUIRE_REAL_MODEL"):
        model_service.ModelService()


def test_existing_corrupt_artifact_fails_instead_of_becoming_demo(tmp_path, monkeypatch):
    artifact = tmp_path / "model.pkl"
    artifact.write_bytes(b"broken")
    monkeypatch.setattr(model_service, "MODEL_FILE", artifact)
    with pytest.raises(RuntimeError, match="Unable to load trained model"):
        model_service._load_real_bundle()


def test_incompatible_sklearn_artifact_is_rejected(tmp_path, monkeypatch):
    from sklearn.exceptions import InconsistentVersionWarning

    artifact = tmp_path / "model.pkl"
    artifact.touch()
    monkeypatch.setattr(model_service, "MODEL_FILE", artifact)

    def incompatible_load(path):
        warnings.warn(InconsistentVersionWarning(
            estimator_name="RandomForestClassifier", current_sklearn_version="1.9.0",
            original_sklearn_version="1.8.0",
        ))
        return bundle()

    monkeypatch.setattr(model_service.joblib, "load", incompatible_load)
    with pytest.raises(RuntimeError, match="matching scikit-learn version"):
        model_service._load_real_bundle()


def test_embedded_metadata_takes_priority_over_stale_sidecar(tmp_path, monkeypatch):
    (tmp_path / "model_meta.json").write_text(json.dumps({"auc_all": 1.0}))
    monkeypatch.setattr(model_service, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(model_service, "_load_real_bundle", bundle)
    monkeypatch.delenv("REQUIRE_REAL_MODEL", raising=False)
    service = model_service.ModelService()
    assert service.model_info()["meta"]["auc_all"] == 0.9
