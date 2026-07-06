"""
model_service.py — model loading, prediction, and SHAP explanation for the
West Africa Variant Screener web app.

Behavior:
    1. If a real trained model exists at outputs/models/variant_screener_v1.pkl
       (produced by `python src/models/train.py`), it is loaded and used as-is.
    2. If it does not exist yet (e.g. fresh clone, data pipeline not run),
       a small synthetic model is trained in-memory on startup so the demo
       is fully interactive. This is clearly flagged to the frontend via
       `demo_mode: true` in /api/model-info — it is NOT presented as the
       real research result.

Feature order is the single source of truth shared with train.py / app.py:
    allele_freq_afr, cadd_score, gene_region, conservation_phylop,
    is_hbb, review_stars
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.config import MODEL_FILE, MODELS_DIR, CADD_DELETERIOUS_THRESHOLD  # noqa: E402

FEATURE_COLS = [
    "allele_freq_afr",
    "cadd_score",
    "gene_region",
    "conservation_phylop",
    "is_hbb",
    "review_stars",
]

FEATURE_LABELS = {
    "allele_freq_afr": "AFR allele frequency",
    "cadd_score": "CADD deleteriousness score",
    "gene_region": "Gene region",
    "conservation_phylop": "Conservation (phyloP)",
    "is_hbb": "HBB gene flag",
    "review_stars": "ClinVar review quality",
}

GENE_REGION_MAP = {"Exonic (coding)": 2, "UTR (untranslated)": 1, "Intronic / other": 0}
HBB_GENES = {"HBB", "HBB-LCR"}

try:
    import shap  # type: ignore
    SHAP_AVAILABLE = True
except Exception:
    SHAP_AVAILABLE = False


def _synthesize_training_set(n: int = 4000, seed: int = 42):
    """
    Generates a biologically-plausible synthetic dataset that mirrors the
    real feature engineering in src/data/build_features.py, so the demo
    model behaves sensibly (rare + high-CADD + conserved => pathogenic;
    common + low-CADD => benign) even before real ClinVar/1000G data is
    downloaded and the real pipeline is run.
    """
    rng = np.random.default_rng(seed)

    label = rng.binomial(1, 0.28, size=n)  # pathogenic minority, like ClinVar

    allele_freq = np.where(
        label == 1,
        rng.beta(0.4, 20, size=n),          # pathogenic: usually rare
        rng.beta(1.2, 3.5, size=n),          # benign: broader, often common
    )
    cadd = np.where(
        label == 1,
        rng.normal(27, 7, size=n).clip(0, 60),
        rng.normal(9, 6, size=n).clip(0, 60),
    )
    conservation = np.where(
        label == 1,
        rng.normal(1.6, 0.9, size=n).clip(-3, 3),
        rng.normal(0.0, 1.1, size=n).clip(-3, 3),
    )
    gene_region = np.where(
        label == 1,
        rng.choice([2, 1, 0], size=n, p=[0.72, 0.13, 0.15]),
        rng.choice([2, 1, 0], size=n, p=[0.35, 0.20, 0.45]),
    )
    is_hbb = np.where(
        label == 1,
        rng.binomial(1, 0.22, size=n),
        rng.binomial(1, 0.05, size=n),
    )
    review_stars = rng.choice([0, 1, 2, 3], size=n, p=[0.15, 0.45, 0.30, 0.10])

    X = np.column_stack([allele_freq, cadd, gene_region, conservation, is_hbb, review_stars])
    return X, label


def _train_demo_model():
    X, y = _synthesize_training_set()
    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_split=6,
        random_state=42, n_jobs=-1, class_weight="balanced",
    )
    model.fit(X, y)
    return {
        "model": model,
        "scaler": None,
        "feature_names": FEATURE_COLS,
        "model_type": "random_forest_demo",
        "auc": None,
        "training_size": len(X),
    }


class ModelService:
    def __init__(self):
        self.demo_mode = False
        self.bundle = None
        self.meta = {}
        self._explainer = None
        self._load()

    def _load(self):
        if MODEL_FILE.exists():
            self.bundle = joblib.load(MODEL_FILE)
            self.demo_mode = False
        else:
            self.bundle = _train_demo_model()
            self.demo_mode = True

        meta_path = MODELS_DIR / "model_meta.json"
        if meta_path.exists() and not self.demo_mode:
            with open(meta_path) as f:
                self.meta = json.load(f)
        else:
            self.meta = {
                "model_type": self.bundle.get("model_type", "random_forest_demo"),
                "auc_all": None,
                "cv_mean": None,
                "cv_std": None,
                "training_variants": self.bundle.get("training_size"),
                "feature_names": FEATURE_COLS,
            }

        if SHAP_AVAILABLE:
            try:
                self._explainer = shap.TreeExplainer(self.bundle["model"])
            except Exception:
                self._explainer = None

    def info(self) -> dict:
        return {
            "demo_mode": self.demo_mode,
            "model_type": self.meta.get("model_type"),
            "auc_all": self.meta.get("auc_all"),
            "cv_mean": self.meta.get("cv_mean"),
            "cv_std": self.meta.get("cv_std"),
            "training_variants": self.meta.get("training_variants"),
            "feature_names": FEATURE_COLS,
            "cadd_threshold": CADD_DELETERIOUS_THRESHOLD,
        }

    def predict(self, allele_freq_afr, cadd_score, gene_region, conservation_phylop, gene_name):
        is_hbb = 1 if gene_name.strip().upper() in HBB_GENES else 0
        review_stars = 1

        values = {
            "allele_freq_afr": float(allele_freq_afr),
            "cadd_score": float(cadd_score),
            "gene_region": GENE_REGION_MAP.get(gene_region, 0),
            "conservation_phylop": float(conservation_phylop),
            "is_hbb": is_hbb,
            "review_stars": review_stars,
        }

        feature_order = self.bundle.get("feature_names") or FEATURE_COLS
        X = np.array([[values[name] for name in feature_order]])

        model = self.bundle["model"]
        scaler = self.bundle.get("scaler")
        X_model = scaler.transform(X) if scaler is not None else X

        prob = float(model.predict_proba(X_model)[0][1])

        if prob >= 0.75:
            label, tier = "Likely Pathogenic", "high"
        elif prob >= 0.40:
            label, tier = "Uncertain / Borderline", "medium"
        else:
            label, tier = "Likely Benign", "low"

        contributions = self._contributions(X_model, feature_order, prob)

        lines = []
        if allele_freq_afr > 0.05:
            lines.append(
                f"AFR frequency {allele_freq_afr:.3f} is common in West African populations — "
                "high-frequency variants are usually not severely pathogenic (unless protective)."
            )
        elif allele_freq_afr < 0.001:
            lines.append(
                f"AFR frequency {allele_freq_afr:.4f} is very rare — "
                "rare variants are more likely to be deleterious."
            )
        if cadd_score >= CADD_DELETERIOUS_THRESHOLD:
            lines.append(
                f"CADD score {cadd_score:.1f} exceeds the deleterious threshold "
                f"({CADD_DELETERIOUS_THRESHOLD:.0f}) — predicted to disrupt protein function."
            )
        else:
            lines.append(
                f"CADD score {cadd_score:.1f} is below the deleterious threshold "
                f"({CADD_DELETERIOUS_THRESHOLD:.0f})."
            )
        if is_hbb:
            lines.append(
                "This is an HBB gene variant — associated with sickle-cell disease or "
                "beta-thalassemia. Interpret in full clinical context."
            )

        return {
            "label": label,
            "tier": tier,
            "probability": round(prob * 100, 1),
            "interpretation": lines,
            "contributions": contributions,
            "is_hbb": bool(is_hbb),
            "gene_region": gene_region,
            "demo_mode": self.demo_mode,
        }

    def _contributions(self, X_model, feature_order, prob):
        """Per-feature push toward pathogenic (+) or benign (-), 0..1 scale for the UI."""
        if self._explainer is not None:
            try:
                sv = self._explainer.shap_values(X_model)
                # shap returns either a 2-class list or a single array depending on version
                if isinstance(sv, list):
                    row = np.array(sv[1][0])
                else:
                    row = np.array(sv[0])
                    if row.ndim > 1:
                        row = row[:, 1]
                max_abs = max(np.abs(row).max(), 1e-6)
                return [
                    {
                        "feature": FEATURE_LABELS.get(name, name),
                        "value": round(float(X_model[0][i]), 3),
                        "push": round(float(row[i]) / max_abs, 3),
                    }
                    for i, name in enumerate(feature_order)
                ]
            except Exception:
                pass

        # Fallback: RF feature_importances_ signed by whether the feature sits
        # above/below the training-set median (a rough, honest approximation
        # when SHAP isn't available in the runtime).
        model = self.bundle["model"]
        importances = getattr(model, "feature_importances_", np.ones(len(feature_order)) / len(feature_order))
        max_imp = max(importances.max(), 1e-6)
        out = []
        for i, name in enumerate(feature_order):
            direction = 1 if X_model[0][i] >= np.median(X_model[0]) else -1
            out.append({
                "feature": FEATURE_LABELS.get(name, name),
                "value": round(float(X_model[0][i]), 3),
                "push": round(direction * float(importances[i]) / max_imp, 3),
            })
        return out


service = ModelService()
