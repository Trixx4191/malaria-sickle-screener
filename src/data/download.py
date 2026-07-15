"""
download.py — automated download of all public datasets.

Usage:
    python src/data/download.py --dataset all
    python src/data/download.py --dataset clinvar
    python src/data/download.py --dataset 1kg
"""

import argparse
import gzip
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path

import requests
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import (
    CLINVAR_URL, KG_PANEL_URL, CADD_API_BASE, CADD_VERSION, GNOMAD_API,
    DATA_RAW, DATA_EXTERNAL, NCBI_API_KEY, NCBI_EMAIL,
    TARGET_GENES, CADD_CACHE
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _download_with_progress(url: str, dest: Path, desc: str = "") -> Path:
    """Download a file with a tqdm progress bar."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f, tqdm(
        desc=desc or dest.name, total=total, unit="B", unit_scale=True
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    return dest


def _gunzip(src: Path, dest: Path) -> Path:
    """Decompress a .gz file."""
    print(f"  Decompressing {src.name}…")
    with gzip.open(src, "rb") as f_in, open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    src.unlink()  # remove the .gz after extraction
    return dest


# ─── Dataset downloaders ──────────────────────────────────────────────────────

def download_clinvar() -> Path:
    """
    Download ClinVar variant_summary.txt from NCBI FTP.
    No API key required, but an NCBI key doubles your rate limit.
    """
    print("\n[1/4] Downloading ClinVar variant summary…")
    url = CLINVAR_URL
    if NCBI_API_KEY:
        url += f"?api_key={NCBI_API_KEY}"

    gz_path  = DATA_RAW / "variant_summary.txt.gz"
    txt_path = DATA_RAW / "variant_summary.txt"

    if txt_path.exists():
        print(f"  Already exists: {txt_path}. Skipping.")
        return txt_path

    _download_with_progress(url, gz_path, desc="ClinVar (.gz)")
    return _gunzip(gz_path, txt_path)


def download_1kg_panel() -> Path:
    """
    Download the 1000 Genomes sample panel file (which populations are which).
    This file is small (~1 MB) and lists which sample belongs to which population.
    """
    print("\n[2/4] Downloading 1000 Genomes sample panel…")
    dest = DATA_RAW / "1kg_panel.tsv"

    if dest.exists():
        print(f"  Already exists: {dest}. Skipping.")
        return dest

    return _download_with_progress(KG_PANEL_URL, dest, desc="1KG panel")


def fetch_cadd_scores(variants: list[dict]) -> dict:
    """
    Query CADD API for a list of variants.
    Each variant: {'chr': '11', 'pos': 5246696, 'ref': 'A', 'alt': 'T'}
    Returns: {variant_key: cadd_score}

    Rate limit: 1 request/second. Results cached locally.
    No API key required.
    """
    print(f"\n[3/4] Fetching CADD scores for {len(variants)} variants…")

    # Load cache
    cache: dict = {}
    if CADD_CACHE.exists():
        with open(CADD_CACHE) as f:
            cache = json.load(f)

    # Only pre-populate results with successful cache hits. A cached None
    # means an earlier run failed to resolve that variant (bad URL, 404,
    # rate limit, etc) — that's not a real answer, so retry it rather than
    # treating "we don't know" as a permanently cached verdict.
    stale_none_count = sum(1 for v in cache.values() if v is None)
    if stale_none_count:
        print(f"  Ignoring {stale_none_count} cached null result(s) — will retry them.")
    results = {k: v for k, v in cache.items() if v is not None}
    new_fetches = 0
    consecutive_failures = 0
    consecutive_404s = 0

    for v in tqdm(variants, desc="CADD API"):
        key = f"{v['chr']}-{v['pos']}-{v['ref']}-{v['alt']}"
        if key in results:
            continue

        url = f"{CADD_API_BASE}{CADD_VERSION}/{v['chr']}:{v['pos']}_{v['ref']}_{v['alt']}"
        score = None
        was_404 = False
        for attempt in range(5):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else min(60, 2 ** attempt * 3)
                    time.sleep(wait)
                    continue
                if resp.status_code == 404:
                    was_404 = True
                    if new_fetches == 0 and consecutive_failures < 3:
                        # print the raw response for the first few failures only,
                        # so we can see the real cause without flooding the log
                        print(f"\n  [debug] {url} -> 404. Body: {resp.text[:200]!r}")
                    break  # not found is not retryable — variant genuinely absent, or URL is wrong
                if resp.status_code != 200:
                    if new_fetches == 0 and consecutive_failures < 3:
                        print(f"\n  [debug] {url} -> {resp.status_code}. Body: {resp.text[:200]!r}")
                    break
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    if new_fetches == 0 and consecutive_failures < 3:
                        print(f"\n  [debug] {url} -> 200 but empty list (CADD has no score for this exact ref/alt).")
                    break
                # Single-SNV endpoint returns [{"Chrom":.., "Ref":.., "Alt":.., "PHRED":..}]
                # — a list of ONE dict, not a list-of-lists like the range endpoint.
                raw = data[0].get("PHRED") if isinstance(data[0], dict) else None
                score = float(raw) if raw is not None else None
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                time.sleep(min(20, 2 ** attempt * 2))
            except Exception as e:
                print(f"  Warning: CADD fetch failed for {key}: {e}")
                break

        results[key] = score  # None if genuinely unresolvable — never faked
        if score is None:
            consecutive_failures += 1
            consecutive_404s = consecutive_404s + 1 if was_404 else 0
            if consecutive_404s >= 15:
                print("\n" + "!" * 60)
                print(f"CADD API returned 404 for {consecutive_404s} lookups in a row.")
                print("This is NOT rate-limiting — it means the request URL itself is")
                print(f"wrong (check CADD_VERSION='{CADD_VERSION}' is a real CADD release)")
                print("or these variants genuinely aren't in CADD's precomputed set.")
                print("Fix the URL/version before re-running, or fetching will keep 404ing.")
                print("!" * 60)
                break
            if consecutive_failures >= 15:
                print("\n" + "!" * 60)
                print(f"CADD API has failed {consecutive_failures} lookups in a row —")
                print("likely persistently rate-limited or unreachable. Stopping instead")
                print("of continuing to hammer it. Already-fetched scores are cached.")
                print("!" * 60)
                break
        else:
            consecutive_failures = 0
            consecutive_404s = 0
            new_fetches += 1
            time.sleep(1.0)   # respect rate limit

    # Save updated cache
    with open(CADD_CACHE, "w") as f:
        json.dump(results, f)

    print(f"  Fetched {new_fetches} new scores. Total cache: {len(results)}.")
    return results


def fetch_gnomad_afr_freq(variant_ids: list[str]) -> dict:
    """
    Query gnomAD GraphQL API for AFR allele frequency.
    variant_ids: list of strings like '11-5246696-A-T'
    Returns: {variant_id: afr_freq}

    No API key required.
    """
    print(f"\n[4/4] Querying gnomAD for AFR frequencies ({len(variant_ids)} variants)…")

    results = {}
    query = """
    query VariantFreq($variantId: String!, $dataset: DatasetId!) {
      variant(variantId: $variantId, dataset: $dataset) {
        genome {
          populations {
            id
            ac
            an
          }
        }
      }
    }
    """

    for vid in tqdm(variant_ids, desc="gnomAD"):
        try:
            resp = requests.post(
                GNOMAD_API,
                json={"query": query, "variables": {"variantId": vid, "dataset": "gnomad_r4"}},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            pops = (
                data.get("data", {})
                    .get("variant", {})
                    .get("genome", {})
                    .get("populations", [])
            ) or []

            afr_ac, afr_an = 0, 0
            for pop in pops:
                if pop["id"] == "afr":
                    afr_ac = pop["ac"] or 0
                    afr_an = pop["an"] or 0
                    break

            freq = afr_ac / afr_an if afr_an > 0 else 0.0
            results[vid] = round(freq, 6)
            time.sleep(0.3)  # be polite to the API

        except Exception as e:
            print(f"  Warning: gnomAD fetch failed for {vid}: {e}")
            results[vid] = None

    return results


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download project datasets")
    parser.add_argument(
        "--dataset",
        choices=["all", "clinvar", "1kg", "cadd", "gnomad"],
        default="all",
        help="Which dataset to download"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("West Africa Variant Screener — Data Download")
    print("=" * 60)

    if args.dataset in ("all", "clinvar"):
        path = download_clinvar()
        print(f"  ✓ ClinVar saved to: {path}")

    if args.dataset in ("all", "1kg"):
        path = download_1kg_panel()
        print(f"  ✓ 1KG panel saved to: {path}")

    if args.dataset in ("all",):
        print("\nNote: CADD and gnomAD are queried per-variant during feature building.")
        print("      Run: python src/data/build_features.py to trigger those API calls.")

    print("\nManual step required:")
    print("  MalariaGEN Pf7 — register at https://malariagen.net/data/pf7")
    print("  After approval, download pf7_samples.txt to data/raw/")
    print("\nAll done.")


if __name__ == "__main__":
    main()
