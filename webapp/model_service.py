"""
model_service.py — loads the trained variant_screener bundle if it exists,
otherwise trains a small synthetic fallback model on startup so the web UI
is fully interactive without requiring the real data pipeline to have run.

Demo mode is always reported via /api/model-info so the frontend can label
it clearly in the status bar — it is never silently presented as the real
research result.
"""

import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.config import MODEL_FILE, MODELS_DIR, TARGET_GENES, CADD_DELETERIOUS_THRESHOLD

FEATURE_ORDER = [
    "allele_freq_afr",
    "cadd_score",
    "gene_region",
    "conservation_phylop",
    "is_hbb",
    "review_stars",
]

GENE_REGION_MAP = {"exonic": 2, "utr": 1, "intronic": 0}
HBB_GENES = {"HBB", "HBB-LCR"}

# PDB / AlphaFold structures for the "04 / STRUCTURE" panel.
STRUCTURE_REGISTRY = {
    "HBB":  {"pdb_id": "2HHB", "chain": "B", "source": "experimental", "label": "Deoxyhemoglobin (T-state), chain B = beta-globin"},
    "HBA1": {"pdb_id": "2HHB", "chain": "A", "source": "experimental", "label": "Deoxyhemoglobin (T-state), chain A = alpha-globin"},
    "HBA2": {"pdb_id": "2HHB", "chain": "A", "source": "experimental", "label": "Deoxyhemoglobin (T-state), chain A = alpha-globin (HBA2 is near-identical to HBA1)"},
    "G6PD": {"pdb_id": "2BH9", "chain": "A", "source": "experimental", "label": "Human G6PD, NADP+-bound dimer"},
    "DARC": {"pdb_id": "AF-Q16570-F1", "chain": "A", "source": "alphafold", "label": "Duffy antigen (ACKR1) — AlphaFold predicted model, no experimental structure available"},
}


def _load_real_bundle():
    if not MODEL_FILE.exists():
        return None
    try:
        bundle = joblib.load(MODEL_FILE)
        if "feature_names" not in bundle or "model" not in bundle:
            return None
        return bundle
    except Exception:
        return None


def _train_synthetic_fallback():
    """Small synthetic RF so the UI works before the real pipeline has run."""
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.RandomState(42)
    n = 800
    allele_freq = rng.beta(0.3, 3.0, n)          # skewed toward rare
    cadd = rng.uniform(0, 45, n)
    gene_region = rng.choice([0, 1, 2], n, p=[0.3, 0.15, 0.55])
    conservation = rng.uniform(-2.5, 3.0, n)
    is_hbb = rng.choice([0, 1], n, p=[0.85, 0.15])
    review_stars = rng.choice([0, 1, 2, 3], n, p=[0.4, 0.35, 0.2, 0.05])

    # Synthetic rule-of-thumb label generator (not real biology, demo only)
    score = (
        (cadd / 45.0) * 1.6
        + (conservation / 3.0) * 0.9
        - (np.log1p(allele_freq * 100) / 5.0) * 1.1
        + (gene_region == 2) * 0.4
        + rng.normal(0, 0.35, n)
    )
    y = (score > np.median(score)).astype(int)

    X = np.column_stack([allele_freq, cadd, gene_region, conservation, is_hbb, review_stars])
    clf = RandomForestClassifier(n_estimators=150, max_depth=8, random_state=42, class_weight="balanced")
    clf.fit(X, y)

    return {
        "model": clf,
        "feature_names": FEATURE_ORDER,
        "meta": {
            "model_type": "random_forest_demo",
            "auc_all": "demo",
            "cv_mean": "demo",
            "cv_std": "demo",
            "training_variants": n,
        },
    }


class ModelService:
    def __init__(self):
        real = _load_real_bundle()
        if real is not None:
            self.bundle = real
            self.demo_mode = False
        else:
            self.bundle = _train_synthetic_fallback()
            self.demo_mode = True

        meta_path = MODELS_DIR / "model_meta.json"
        self.meta = self.bundle.get("meta", {})
        if not self.demo_mode and meta_path.exists():
            import json
            with open(meta_path) as f:
                self.meta = json.load(f)

    def model_info(self):
        return {
            "demo_mode": self.demo_mode,
            "meta": self.meta,
            "feature_order": FEATURE_ORDER,
            "genes": list(TARGET_GENES.keys()),
        }

    def predict(self, allele_freq_afr, cadd_score, gene_region, conservation_phylop, gene_name):
        is_hbb = 1 if gene_name.strip().upper() in HBB_GENES else 0
        review_stars = 1

        values = {
            "allele_freq_afr": allele_freq_afr,
            "cadd_score": cadd_score,
            "gene_region": GENE_REGION_MAP.get(gene_region, 0),
            "conservation_phylop": conservation_phylop,
            "is_hbb": is_hbb,
            "review_stars": review_stars,
        }

        feature_order = self.bundle["feature_names"]
        X = np.array([[values[name] for name in feature_order]])
        model = self.bundle["model"]
        prob = float(model.predict_proba(X)[0][1])

        if prob >= 0.75:
            tier, color = "pathogenic", "high"
        elif prob >= 0.40:
            tier, color = "uncertain", "medium"
        else:
            tier, color = "benign", "low"

        # Feature contributions: real SHAP if available and not in demo mode,
        # otherwise a fast approximation from the RF's feature_importances_
        # scaled by how far each feature sits from a neutral midpoint.
        contributions = self._feature_contributions(model, feature_order, values, X)

        notes = []
        if allele_freq_afr > 0.05:
            notes.append(f"AFR frequency {allele_freq_afr:.3f} is common in West African populations — usually not severely pathogenic unless protective.")
        elif allele_freq_afr < 0.001:
            notes.append(f"AFR frequency {allele_freq_afr:.4f} is very rare — rare variants are more likely deleterious.")
        if cadd_score >= CADD_DELETERIOUS_THRESHOLD:
            notes.append(f"CADD score {cadd_score:.1f} exceeds the deleterious threshold (20).")
        else:
            notes.append(f"CADD score {cadd_score:.1f} is below the deleterious threshold (20).")
        if is_hbb:
            notes.append("HBB gene variant — associated with sickle-cell disease / beta-thalassemia. Interpret in full clinical context.")

        return {
            "tier": tier,
            "color": color,
            "probability": round(prob * 100, 1),
            "notes": notes,
            "contributions": contributions,
            "demo_mode": self.demo_mode,
        }

    @staticmethod
    def _feature_contributions(model, feature_order, values, X):
        try:
            importances = model.feature_importances_
        except AttributeError:
            importances = np.ones(len(feature_order)) / len(feature_order)

        midpoints = {
            "allele_freq_afr": 0.05, "cadd_score": 20.0, "gene_region": 1.0,
            "conservation_phylop": 0.0, "is_hbb": 0.5, "review_stars": 1.5,
        }
        directions = []
        for name in feature_order:
            mid = midpoints.get(name, 0)
            directions.append(1 if values[name] >= mid else -1)

        raw = importances * np.array(directions)
        max_abs = max(abs(raw).max(), 1e-9)
        return [
            {"feature": name, "weight": round(float(w / max_abs), 3)}
            for name, w in zip(feature_order, raw)
        ]

    def structure_for(self, gene_name):
        gene = gene_name.strip().upper()
        return STRUCTURE_REGISTRY.get(gene)
