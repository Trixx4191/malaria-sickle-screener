"""
build_features.py — assemble the final feature matrix from all data sources.

Columns in the output feature matrix:
    variant_id, gene, allele_freq_afr, cadd_score, gene_region,
    conservation_phylop (CADD-derived proxy), is_hbb, review_stars, label

Run after:
    python src/data/download.py --dataset clinvar

The 1000 Genomes panel is optional reference material, not a feature input.
Real remote lookups are the default; an offline placeholder check requires
FEATURE_BUILD_USE_REMOTE=0 together with --allow-fake. See docs/DATA.md.

Usage:
    python src/data/build_features.py
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
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

    Failed lookups (after retries are exhausted) map to None — NEVER 0.0.
    A None means "we don't know", not "frequency is zero"; build() drops
    those rows rather than silently treating them as real data.
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

    session = requests.Session()

    cache = {}
    if GNOMAD_CACHE.exists():
        with open(GNOMAD_CACHE) as f:
            cache = json.load(f)

    def query_one(vid: str, max_retries: int = 6):
        """Returns a float AFR frequency, or None if genuinely unresolvable
        after retrying through rate limits / transient errors."""
        for attempt in range(max_retries):
            try:
                resp = session.post(
                    GNOMAD_API,
                    json={"query": query, "variables": {"variantId": vid, "dataset": "gnomad_r4"}},
                    timeout=(5, 15),
                )
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else min(60, 2 ** attempt * 3)
                    time.sleep(wait)
                    continue
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
                return round(afr_ac / afr_an, 6) if afr_an > 0 else 0.0
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                time.sleep(min(30, 2 ** attempt * 2))
            except Exception as exc:
                print(f"  Warning: gnomAD lookup failed for {vid}: {exc}")
                return None
        return None  # retries exhausted — genuinely unresolvable, not a zero

    results = {}
    seen = set()
    consecutive_failures = 0
    n_failed = 0
    for vid in tqdm(valid_ids, desc="gnomAD AFR freq"):
        if vid in seen:
            continue
        seen.add(vid)
        if vid in cache:
            results[vid] = cache[vid]
            consecutive_failures = 0
            continue

        value = query_one(vid)
        if value is None:
            n_failed += 1
            consecutive_failures += 1
            results[vid] = None
            if consecutive_failures >= 15:
                print("\n" + "!" * 60)
                print(f"gnomAD has failed {consecutive_failures} lookups in a row — the API")
                print("is likely persistently rate-limiting or unreachable right now.")
                print("Stopping instead of continuing to hammer it. Re-run the script")
                print("later (already-fetched results are cached) rather than letting")
                print("thousands of variants silently fall back to fake values.")
                print("!" * 60)
                break
        else:
            consecutive_failures = 0
            results[vid] = value
            cache[vid] = value
            time.sleep(1.0)  # gnomAD's public API is strict — stay well under its limit

    if cache:
        GNOMAD_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(GNOMAD_CACHE, "w") as f:
            json.dump(cache, f)

    print(f"  gnomAD: {len(results) - n_failed} resolved, {n_failed} unresolved "
          f"(unresolved rows will be dropped, not zero-filled).")
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


def build(allow_fake: bool = False) -> pd.DataFrame:
    print("=" * 60)
    print("Building feature matrix…")
    print("=" * 60)

    # 1. Load ClinVar clean data
    df = load_clinvar_clean()
    print(f"\nLoaded {len(df):,} labelled variants from ClinVar.")

    # 2. Build variant IDs
    df["variant_id_gnomad"] = build_variant_ids(df)

    # Real data (gnomAD + CADD API calls) is the default. Set
    # FEATURE_BUILD_USE_REMOTE=0 AND pass --allow-fake for a deliberately
    # zero-filled offline pipeline check. Such features are synthetic and
    # cannot support reported real-data research results.
    use_remote = os.getenv("FEATURE_BUILD_USE_REMOTE", "1").lower() in {"1", "true", "yes", "on"}

    # No silent cap: fetch every variant unless the caller explicitly sets one.
    max_variants_env = os.getenv("FEATURE_BUILD_MAX_VARIANTS", "")
    max_variants = None
    if max_variants_env.strip():
        try:
            parsed = int(max_variants_env)
            max_variants = parsed if parsed > 0 else None
        except ValueError:
            max_variants = None

    if not use_remote and not allow_fake:
        print("\n" + "!" * 60)
        print("REFUSING TO BUILD: FEATURE_BUILD_USE_REMOTE=0 would zero-fill")
        print("allele_freq_afr and cadd_score instead of fetching real gnomAD/")
        print("CADD values. That produces a fake feature matrix.")
        print("Pass --allow-fake explicitly if this is really what you want")
        print("(e.g. a fast offline pipeline smoke test).")
        print("!" * 60)
        raise SystemExit(1)

    if use_remote:
        print(f"\nFetching REAL data from gnomAD + CADD APIs "
              f"({'all' if max_variants is None else max_variants} variants)…")
        gnomad_map = fetch_all_gnomad(df["variant_id_gnomad"].tolist(), max_variants=max_variants)
        # NOTE: intentionally NOT .fillna(0.0) — a failed/unresolved lookup is
        # unknown, not zero. Rows that stay NaN get dropped below, not faked.
        df["allele_freq_afr"] = df["variant_id_gnomad"].map(gnomad_map)

        cadd_map = fetch_all_cadd(df, max_variants=max_variants)
        def cadd_key(row):
            try:
                return f"{row['chr']}-{int(row['pos'])}-{row['ref']}-{row['alt']}"
            except Exception:
                return None
        df["cadd_key"] = df.apply(cadd_key, axis=1)
        df["cadd_score"] = df["cadd_key"].map(cadd_map)
        data_provenance = "real"
    else:
        print("\n⚠ FAKE DATA MODE (--allow-fake): allele_freq_afr and cadd_score")
        print("  are zero-filled placeholders, not real API values.")
        df["allele_freq_afr"] = 0.0
        df["cadd_score"] = 0.0
        data_provenance = "synthetic_placeholder"

    # 5. Derived features
    # CADD-derived proxy, not measured phyloP. Changing the feature definition
    # requires explicit provenance, retraining and evaluation.
    df["conservation_phylop"] = (df["cadd_score"] / 40.0).clip(-3, 3)

    # 6. Select and order final feature columns
    features = df[[
        "variant_id", "gene",
        "allele_freq_afr",    # gnomAD genome AFR group; not a West African cohort
        "cadd_score",         # deleteriousness
        "gene_region",        # exonic=2, UTR=1, intronic=0
        "conservation_phylop",# conservation (CADD-derived proxy)
        "is_hbb",             # sickle-cell gene flag
        "review_stars",       # ClinVar evidence quality
        "label",              # TARGET: 1=pathogenic, 0=benign
    ]].copy()

    # 7. Drop rows with missing critical values (includes unresolved gnomAD/
    # CADD lookups represented as NaN. gnomAD HTTP-success responses without
    # usable population data can still become zero; see docs/DATA.md.
    n_before = len(features)
    n_missing_af = features["allele_freq_afr"].isna().sum()
    n_missing_cadd = features["cadd_score"].isna().sum()
    features = features.dropna(subset=["cadd_score", "allele_freq_afr", "label"])
    n_dropped = n_before - len(features)
    print(f"\nDropped {n_dropped} rows with missing features "
          f"({n_missing_af} unresolved gnomAD, {n_missing_cadd} unresolved CADD).")
    if use_remote and n_before > 0 and n_dropped / n_before > 0.3:
        print("⚠ More than 30% of variants were dropped due to failed API lookups.")
        print("  Consider re-running later if the APIs were rate-limiting you —")
        print("  already-resolved variants are cached and won't be re-fetched.")
    print(f"Final matrix: {len(features):,} variants × {features.shape[1]} columns")
    print(f"\nLabel distribution:")
    print(features["label"].value_counts().to_string())
    print(f"\nGene distribution:")
    print(features["gene"].value_counts().to_string())

    # 8. Save feature matrix + a sidecar provenance file. train.py copies this
    # into model_meta.json so the web UI can show whether the served model
    # was trained on real gnomAD/CADD data or a placeholder matrix.
    FEATURE_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURE_MATRIX, index=False)
    provenance_path = FEATURE_MATRIX.with_name("features_provenance.json")
    with open(provenance_path, "w") as f:
        json.dump({
            "data_provenance": data_provenance,
            "n_variants": len(features),
            "n_dropped_unresolved_lookups": int(n_dropped) if use_remote else 0,
            "max_variants_fetched": max_variants,
        }, f, indent=2)
    print(f"\n✓ Feature matrix saved to: {FEATURE_MATRIX}")
    print(f"✓ Provenance saved to: {provenance_path}  (data_provenance={data_provenance})")

    if data_provenance != "real":
        print("\n⚠ This feature matrix does NOT contain real gnomAD/CADD data.")
        print("  Do not report results trained on this matrix as the research result.")

    return features


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-fake", action="store_true",
                         help="Allow building a zero-filled placeholder matrix "
                              "(FEATURE_BUILD_USE_REMOTE=0). Off by default — "
                              "real data is the default behavior.")
    args = parser.parse_args()
    build(allow_fake=args.allow_fake)
