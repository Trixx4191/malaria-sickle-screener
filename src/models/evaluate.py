"""
evaluate.py — SHAP explainability and evaluation plots.

Generates:
    outputs/figures/shap_summary.png       — global feature importance
    outputs/figures/shap_beeswarm.png      — beeswarm detail plot
    outputs/figures/feature_importance.png — RF feature importance bar

Usage:
    python src/models/evaluate.py
"""

import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import MODEL_FILE, FEATURE_MATRIX, FIGURES

FEATURE_COLS = [
    "allele_freq_afr",
    "cadd_score",
    "gene_region",
    "conservation_phylop",
    "is_hbb",
    "review_stars",
]

FEATURE_LABELS = {
    "allele_freq_afr":     "AFR allele frequency",
    "cadd_score":          "CADD score",
    "gene_region":         "Gene region (exonic/UTR/intronic)",
    "conservation_phylop": "Conservation (phyloP proxy)",
    "is_hbb":              "HBB gene flag (sickle-cell)",
    "review_stars":        "ClinVar review quality",
}


def load_model_and_data():
    bundle = joblib.load(MODEL_FILE)
    df = pd.read_csv(FEATURE_MATRIX)
    X = df[FEATURE_COLS].values
    y = df["label"].values
    return bundle, X, y, df


def run_shap(model, X: np.ndarray, feature_names: list[str]):
    print("Computing SHAP values (this takes 1–3 min for large datasets)…")
    # Use a background sample for speed
    background = shap.sample(X, min(200, len(X)), random_state=42)
    explainer = shap.TreeExplainer(model, background)
    shap_values = explainer(X[:500])   # explain first 500 for speed
    return shap_values


def plot_shap_summary(shap_values, feature_names: list[str]):
    fig, ax = plt.subplots(figsize=(9, 5))
    shap.plots.bar(shap_values, max_display=len(feature_names),
                   show=False, ax=ax)
    ax.set_title(
        "Feature importance (SHAP) — West Africa Variant Screener",
        fontsize=12, pad=12
    )
    ax.set_xlabel("Mean |SHAP value| (impact on pathogenicity prediction)")
    # Rename y-tick labels
    labels = [FEATURE_LABELS.get(t.get_text(), t.get_text())
              for t in ax.get_yticklabels()]
    ax.set_yticklabels(labels)
    plt.tight_layout()
    path = FIGURES / "shap_summary.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ SHAP summary saved: {path}")


def plot_shap_beeswarm(shap_values, feature_names: list[str]):
    fig, ax = plt.subplots(figsize=(9, 6))
    shap.plots.beeswarm(shap_values, max_display=len(feature_names),
                        show=False)
    plt.title("SHAP beeswarm — individual variant explanations", fontsize=12)
    plt.tight_layout()
    path = FIGURES / "shap_beeswarm.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ SHAP beeswarm saved: {path}")


def plot_rf_importance(model, feature_names: list[str]):
    importances = model.feature_importances_
    labels = [FEATURE_LABELS.get(f, f) for f in feature_names]
    order = np.argsort(importances)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(
        [labels[i] for i in order],
        importances[order],
        color="#1D9E75", edgecolor="none", height=0.55
    )
    ax.set_xlabel("Gini importance")
    ax.set_title("Random Forest feature importance", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = FIGURES / "feature_importance.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  ✓ Feature importance saved: {path}")


def main():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_FILE}.\n"
            "Run: python src/models/train.py"
        )

    print("=" * 60)
    print("Evaluating model with SHAP…")
    print("=" * 60)

    bundle, X, y, df = load_model_and_data()
    model = bundle["model"]
    feature_names = bundle["feature_names"]

    FIGURES.mkdir(parents=True, exist_ok=True)

    shap_values = run_shap(model, X, feature_names)
    plot_shap_summary(shap_values, feature_names)
    plot_shap_beeswarm(shap_values, feature_names)
    plot_rf_importance(model, feature_names)

    print("\nAll evaluation figures saved to:", FIGURES)


if __name__ == "__main__":
    main()
