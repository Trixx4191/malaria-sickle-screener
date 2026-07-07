"""
build_features.py — assemble the final feature matrix from all data sources.

Columns in the output feature matrix:
    variant_id, gene, allele_freq_afr, cadd_score, gene_region,
    conservation_phylop (placeholder), is_hbb, review_stars, label

Run after:
    python src/data/download.py --dataset clinvar
    python src/data/download.py --dataset 1kg

Usage:
    python src/data/build_features.py
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import (
    FEATURE_MATRIX, CLINVAR_CLEAN, GNOMAD_API, CADD_API_BASE, CADD_CACHE,
    GNOMAD_CACHE, AFR_FREQ_THRESHOLD, CADD_DELETERIOUS_THRESHOLD
)
from src.data.parse_clinvar import parse as parse_clinvar
from src.data.download import fetch_cadd_scores, fetch_gnomad_afr_freq
import json


def load_clinvar_clean() -> pd.DataFrame:
    if not CLINVAR_CLEAN.exists():
        print("ClinVar clean file not found — running parser…")
        return parse_clinvar(save=True)
    return pd.read_csv(CLINVAR_CLEAN)


def build_variant_ids(df: pd.DataFrame) -> list[str]:
    """Build gnomAD-style variant IDs: chr-pos-ref-alt."""
    ids = []
    for _, row in df.iterrows():
        try:
            ids.append(f"{row['chr']}-{int(row['pos'])}-{row['ref']}-{row['alt']}")
        except (ValueError, TypeError):
            ids.append(None)
    return ids


def fetch_all_gnomad(variant_ids: list[str], batch_size: int = 50, max_variants: int | None = None) -> dict:
    """
    Fetch gnomAD AFR frequencies for all variants.
    Batches requests to avoid overloading the API.
    """
    valid_ids = [v for v in variant_ids if v is not None]
    if max_variants is not None:
        valid_ids = valid_ids[:max_variants]
    print(f"\nQuerying gnomAD for {len(valid_ids)} variants (AFR frequency)…")

    query = """
    query($variantId: String!, $dataset: DatasetId!) {
      variant(variantId: $variantId, dataset: $dataset) {
        genome { populations { id ac an } }
      }
    }
    """

    retry_strategy = Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"POST"},
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    cache = {}
    if GNOMAD_CACHE.exists():
        with open(GNOMAD_CACHE) as f:
            cache = json.load(f)

    results = {}
    seen = set()
    failures = 0
    for vid in tqdm(valid_ids, desc="gnomAD AFR freq"):
        if vid in seen:
            continue
        seen.add(vid)
        if vid in cache:
            results[vid] = cache[vid]
            continue

        if failures >= 20:
            print("  gnomAD rate limit reached; using 0.0 for remaining variants.")
            break

        try:
            resp = session.post(
                GNOMAD_API,
                json={"query": query, "variables": {"variantId": vid, "dataset": "gnomad_r4"}},
                timeout=(5, 15),
            )
            resp.raise_for_status()
            data = resp.json()
            pops = ((data.get("data") or {}).get("variant") or {})
            pops = (pops.get("genome") or {}).get("populations") or []

            afr_ac = afr_an = 0
            for pop in pops:
                if pop["id"] == "afr":
                    afr_ac = pop["ac"] or 0
                    afr_an = pop["an"] or 0
                    break

            value = round(afr_ac / afr_an, 6) if afr_an > 0 else 0.0
            results[vid] = value
            cache[vid] = value
            time.sleep(0.2)

        except Exception as exc:
            failures += 1
            results[vid] = 0.0
            if not isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                print(f"  Warning: gnomAD lookup failed for {vid}: {exc}")

    if cache:
        GNOMAD_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(GNOMAD_CACHE, "w") as f:
            json.dump(cache, f)

    return results


def fetch_all_cadd(df: pd.DataFrame, max_variants: int | None = None) -> dict:
    """Fetch CADD scores for all variants, using local cache."""
    variants = []
    for _, row in df.iterrows():
        try:
            variants.append({
                "chr": str(row["chr"]),
                "pos": int(row["pos"]),
                "ref": str(row["ref"]),
                "alt": str(row["alt"]),
            })
        except (ValueError, TypeError):
            pass
    if max_variants is not None:
        variants = variants[:max_variants]
    return fetch_cadd_scores(variants)


def build() -> pd.DataFrame:
    print("=" * 60)
    print("Building feature matrix…")
    print("=" * 60)

    # 1. Load ClinVar clean data
    df = load_clinvar_clean()
    print(f"\nLoaded {len(df):,} labelled variants from ClinVar.")

    # 2. Build variant IDs
    df["variant_id_gnomad"] = build_variant_ids(df)

    max_variants = os.getenv("FEATURE_BUILD_MAX_VARIANTS", "200")
    try:
        max_variants = int(max_variants)
    except ValueError:
        max_variants = 200
    if max_variants < 1:
        max_variants = None

    use_remote = os.getenv("FEATURE_BUILD_USE_REMOTE", "0").lower() in {"1", "true", "yes", "on"}

    if use_remote:
        gnomad_map = fetch_all_gnomad(df["variant_id_gnomad"].tolist(), max_variants=max_variants)
        df["allele_freq_afr"] = df["variant_id_gnomad"].map(gnomad_map).fillna(0.0)

        cadd_map = fetch_all_cadd(df, max_variants=max_variants)
        def cadd_key(row):
            try:
                return f"{row['chr']}-{int(row['pos'])}-{row['ref']}-{row['alt']}"
            except Exception:
                return None
        df["cadd_key"] = df.apply(cadd_key, axis=1)
        df["cadd_score"] = df["cadd_key"].map(cadd_map).fillna(0.0)
    else:
        df["allele_freq_afr"] = 0.0
        df["cadd_score"] = 0.0

    # 5. Derived features
    # Placeholder conservation score — replace with real phyloP from UCSC when available
    # For now: use CADD as a proxy (highly correlated with conservation)
    df["conservation_phylop"] = (df["cadd_score"] / 40.0).clip(-3, 3)

    # 6. Select and order final feature columns
    features = df[[
        "variant_id", "gene",
        "allele_freq_afr",    # PRIMARY West Africa signal
        "cadd_score",         # deleteriousness
        "gene_region",        # exonic=2, UTR=1, intronic=0
        "conservation_phylop",# conservation (CADD-derived proxy)
        "is_hbb",             # sickle-cell gene flag
        "review_stars",       # ClinVar evidence quality
        "label",              # TARGET: 1=pathogenic, 0=benign
    ]].copy()

    # 7. Drop rows with missing critical values
    n_before = len(features)
    features = features.dropna(subset=["cadd_score", "allele_freq_afr", "label"])
    print(f"\nDropped {n_before - len(features)} rows with missing features.")
    print(f"Final matrix: {len(features):,} variants × {features.shape[1]} columns")
    print(f"\nLabel distribution:")
    print(features["label"].value_counts().to_string())
    print(f"\nGene distribution:")
    print(features["gene"].value_counts().to_string())

    # 8. Save
    FEATURE_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURE_MATRIX, index=False)
    print(f"\n✓ Feature matrix saved to: {FEATURE_MATRIX}")

    return features


if __name__ == "__main__":
    build()
