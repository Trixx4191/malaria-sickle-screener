import numpy as np
from sklearn.datasets import make_classification

from src.models import train


def test_smote_never_sees_cv_validation_or_held_out_rows(monkeypatch):
    X, y = make_classification(n_samples=120, n_features=6, n_informative=4,
                               n_redundant=0, weights=[0.7, 0.3], random_state=7)
    X[:, 0] = np.arange(len(X))
    X_train, X_test, y_train, y_test = X[:96], X[96:], y[:96], y[96:]
    sampled_rows = []
    original = train.SMOTE.fit_resample

    def observe_resample(sampler, features, labels, **kwargs):
        sampled_rows.append(set(features[:, 0]))
        return original(sampler, features, labels, **kwargs)

    monkeypatch.setattr(train.SMOTE, "fit_resample", observe_resample)
    monkeypatch.setattr(train, "CV_FOLDS", 3)
    monkeypatch.setattr(train, "RF_PARAMS", {"n_estimators": 4, "max_depth": 3,
                                            "random_state": 42, "n_jobs": 1})
    result = train.train_random_forest(X_train, y_train, X_test, y_test)

    assert len(sampled_rows) == 4
    training_rows = set(X_train[:, 0])
    assert all(rows < training_rows for rows in sampled_rows[:-1])
    assert sampled_rows[-1] == training_rows
    assert result["test_variants"] == len(y_test)


class RecordingModel:
    def predict_proba(self, X):
        self.received = X.copy()
        probability = X[:, 1]
        return np.column_stack([1 - probability, probability])


def test_afr_metric_uses_only_test_rows_above_threshold():
    X_test = np.zeros((20, len(train.FEATURE_COLS)))
    X_test[:10, 0] = 0.1
    X_test[:10, 1] = np.tile([0.1, 0.9], 5)
    y_test = np.tile([0, 1], 10)
    model = RecordingModel()
    result = train.evaluate_afr_subset({"model": model, "scaler": None}, X_test, y_test)

    np.testing.assert_array_equal(model.received, X_test[:10])
    assert result == {"evaluation_set": "held_out_test", "variants": 10,
                      "benign": 5, "pathogenic": 5, "auc": 1.0}


def test_afr_auc_is_skipped_for_single_class_subset():
    X_test = np.zeros((12, len(train.FEATURE_COLS)))
    X_test[:, 0] = 0.1
    model = RecordingModel()
    result = train.evaluate_afr_subset({"model": model}, X_test, np.zeros(12))
    assert result["auc"] is None
    assert result["variants"] == 12
    assert not hasattr(model, "received")
