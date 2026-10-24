"""
train.py — full model training pipeline.

Trains a Logistic Regression baseline and a Random Forest with SMOTE.
Saves the best model to outputs/models/variant_screener_v1.pkl

Usage:
    python src/models/train.py
    python src/models/train.py --model logistic   # baseline only
    python src/models/train.py --model random_forest
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, roc_auc_score, confusion_matrix,
    ConfusionMatrixDisplay, RocCurveDisplay
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import (
    FEATURE_MATRIX, MODEL_FILE, FIGURES, MODELS_DIR,
    RF_PARAMS, RANDOM_SEED, TEST_SIZE, CV_FOLDS, AFR_FREQ_THRESHOLD
)

FEATURE_COLS = [
    "allele_freq_afr",
    "cadd_score",
    "gene_region",
    "conservation_phylop",
    "is_hbb",
    "review_stars",
]


def load_data_provenance() -> dict:
    """Read the sidecar file build_features.py writes, describing whether
    allele_freq_afr/cadd_score came from real gnomAD/CADD API calls or a
    zero-filled placeholder. Missing file = assume unknown/legacy matrix."""
    provenance_path = FEATURE_MATRIX.with_name("features_provenance.json")
    if not provenance_path.exists():
        return {"data_provenance": "unknown"}
    with open(provenance_path) as f:
        return json.load(f)


def load_features() -> pd.DataFrame:
    if not FEATURE_MATRIX.exists():
        raise FileNotFoundError(
            f"Feature matrix not found at {FEATURE_MATRIX}.\n"
            "Run: python src/data/build_features.py"
        )
    df = pd.read_csv(FEATURE_MATRIX)
    print(f"Loaded {len(df):,} variants. Label distribution:")
    print(df["label"].value_counts().to_string())

    provenance = load_data_provenance()
    if provenance.get("data_provenance") != "real":
        print("\n" + "!" * 60)
        print(f"WARNING: feature matrix data_provenance = "
              f"'{provenance.get('data_provenance')}', not 'real'.")
        print("allele_freq_afr and/or cadd_score may be placeholder values.")
        print("Re-run build_features.py without --allow-fake for a real model.")
        print("!" * 60 + "\n")
    return df


def split(df: pd.DataFrame):
    X = df[FEATURE_COLS].values
    y = df["label"].values
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y)


def train_baseline(X_train, y_train, X_test, y_test) -> dict:
    print("\n── Logistic Regression (baseline) ──────────────────────")
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_train)
    X_te_s = scaler.transform(X_test)

    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED, class_weight="balanced")
    lr.fit(X_tr_s, y_train)

    y_pred = lr.predict(X_te_s)
    y_prob = lr.predict_proba(X_te_s)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print(f"  AUC-ROC : {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["Benign", "Pathogenic"]))

    return {"model": lr, "scaler": scaler, "auc": auc, "type": "logistic",
            "fit_variants": len(y_train), "test_variants": len(y_test)}


def train_random_forest(X_train, y_train, X_test, y_test) -> dict:
    print("\n── Random Forest + SMOTE ───────────────────────────────")

    # Each CV fold must learn its synthetic neighbors from that fold's
    # training rows only. Resampling before CV leaks validation information.
    pipeline = Pipeline([
        ("smote", SMOTE(random_state=RANDOM_SEED)),
        ("model", RandomForestClassifier(**RF_PARAMS)),
    ])
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=1)
    print(f"  {CV_FOLDS}-fold training CV AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    pipeline.fit(X_train, y_train)
    # Save the fitted forest alone: inference does not need the training-only
    # sampler or an imbalanced-learn dependency.
    rf = pipeline.named_steps["model"]

    y_pred = rf.predict(X_test)
    y_prob = rf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print(f"  AUC-ROC : {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["Benign", "Pathogenic"]))

    return {"model": rf, "scaler": None, "auc": auc, "type": "random_forest",
            "cv_mean": cv_scores.mean(), "cv_std": cv_scores.std(),
            "cv_method": "stratified_training_folds_with_fold_local_smote",
            "fit_variants": len(y_train), "test_variants": len(y_test)}


def evaluate_afr_subset(bundle: dict, X_test, y_test):
    """Evaluate high-AFR-frequency variants only within the untouched test set."""
    print("\n── Held-out AFR-frequency Subset Evaluation ────────────")
    afr_mask = X_test[:, FEATURE_COLS.index("allele_freq_afr")] > AFR_FREQ_THRESHOLD
    X_afr = X_test[afr_mask]
    y_afr = y_test[afr_mask]
    result = {
        "evaluation_set": "held_out_test",
        "variants": len(y_afr),
        "benign": int(np.sum(y_afr == 0)),
        "pathogenic": int(np.sum(y_afr == 1)),
        "auc": None,
    }
    if len(y_afr) < 10 or len(np.unique(y_afr)) < 2:
        print(f"  Only {len(y_afr)} held-out AFR variants or fewer than two classes; AUC skipped.")
        return result

    model = bundle["model"]
    if bundle.get("scaler") is not None:
        X_afr = bundle["scaler"].transform(X_afr)

    y_prob = model.predict_proba(X_afr)[:, 1]
    auc = roc_auc_score(y_afr, y_prob)
    print(f"  Held-out AFR subset size: {len(y_afr)} variants")
    print(f"  Held-out AFR subset AUC-ROC: {auc:.4f} (small subsets remain exploratory)")
    result["auc"] = float(auc)
    return result


def plot_roc(bundles: list[dict], X_test, y_test):
    fig, ax = plt.subplots(figsize=(7, 5))
    for b in bundles:
        X = b["scaler"].transform(X_test) if b["scaler"] else X_test
        RocCurveDisplay.from_predictions(
            y_test, b["model"].predict_proba(X)[:, 1],
            name=b["type"].replace("_", " ").title(), ax=ax
        )
    ax.set_title("ROC Curves — Variant Screener", fontsize=13)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    plt.tight_layout()
    path = FIGURES / "roc_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"\n  ROC plot saved: {path}")


def plot_confusion(bundle: dict, X_test, y_test):
    X = bundle["scaler"].transform(X_test) if bundle["scaler"] else X_test
    y_pred = bundle["model"].predict(X)
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=["Benign", "Pathogenic"])
    fig, ax = plt.subplots(figsize=(5, 4))
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Confusion Matrix (Random Forest + SMOTE)")
    plt.tight_layout()
    path = FIGURES / "confusion_matrix.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Confusion matrix saved: {path}")


def save_model(bundle: dict, df: pd.DataFrame):
    feature_order_version = "v1"
    provenance = load_data_provenance()
    # Keep metadata inside the artifact as well as the human-readable sidecar,
    # so an old sidecar cannot change the app's reported evaluation results.
    meta = {
        "model_type": bundle["type"],
        "auc_all": round(float(bundle["auc"]), 4),
        "cv_mean": round(float(bundle["cv_mean"]), 4) if "cv_mean" in bundle else None,
        "cv_std": round(float(bundle["cv_std"]), 4) if "cv_std" in bundle else None,
        "cv_method": bundle.get("cv_method"),
        "evaluation_set": "held_out_test",
        "feature_names": FEATURE_COLS,
        "training_variants": bundle["fit_variants"],
        "test_variants": bundle["test_variants"],
        "total_variants": len(df),
        "afr_subset": bundle.get("afr_subset"),
        "data_provenance": provenance.get("data_provenance", "unknown"),
    }
    payload = {
        "model": bundle["model"],
        "scaler": bundle["scaler"],
        "feature_names": FEATURE_COLS,
        "feature_order_version": feature_order_version,
        "model_type": bundle["type"],
        "auc": bundle["auc"],
        "training_size": bundle["fit_variants"],
        "data_provenance": provenance.get("data_provenance", "unknown"),
        "meta": meta,
    }
    joblib.dump(payload, MODEL_FILE)
    print(f"\n✓ Model saved: {MODEL_FILE}")

    meta_path = MODELS_DIR / "model_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"✓ Metadata saved: {meta_path}  (data_provenance={meta['data_provenance']})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["all", "logistic", "random_forest"],
                        default="all")
    args = parser.parse_args()

    df = load_features()
    X_train, X_test, y_train, y_test = split(df)

    bundles = []

    if args.model in ("all", "logistic"):
        bundles.append(train_baseline(X_train, y_train, X_test, y_test))

    rf_bundle = None
    if args.model in ("all", "random_forest"):
        rf_bundle = train_random_forest(X_train, y_train, X_test, y_test)
        bundles.append(rf_bundle)
        rf_bundle["afr_subset"] = evaluate_afr_subset(rf_bundle, X_test, y_test)

    if len(bundles) >= 2:
        plot_roc(bundles, X_test, y_test)

    best = max(bundles, key=lambda b: b["auc"])
    if rf_bundle:
        plot_confusion(rf_bundle, X_test, y_test)
        save_model(rf_bundle, df)
    else:
        save_model(best, df)

    print("\n" + "=" * 60)
    print(f"Best model: {best['type']} — AUC {best['auc']:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
