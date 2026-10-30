"""
download.py — download ClinVar and the 1000 Genomes sample panel.

CADD and gnomAD helper functions are used during feature construction;
--dataset all downloads the two source files only. No Pf7 step is required.

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
    No API key is required for this static public file. The optional key is
    appended by the current client; E-utilities rate limits do not apply here.
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

    The client pauses one second after successful lookups and caches results.
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
    no_data_count = 0          # legitimate "CADD has no score for this" — not a failure
    consecutive_api_failures = 0  # genuine transport/API problems only

    for v in tqdm(variants, desc="CADD API"):
        key = f"{v['chr']}-{v['pos']}-{v['ref']}-{v['alt']}"
        if key in results:
            continue

        url = f"{CADD_API_BASE}{CADD_VERSION}/{v['chr']}:{v['pos']}_{v['ref']}_{v['alt']}"
        score = None
        api_failed = False  # did the API itself misbehave, vs. give a valid "no data" answer?

        for attempt in range(5):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else min(60, 2 ** attempt * 3)
                    time.sleep(wait)
                    if attempt == 4:
                        api_failed = True  # retries exhausted while still being rate-limited
                    continue
                if resp.status_code == 404:
                    # A "not found" for a well-formed query is CADD telling us it has
                    # no record here (bad ref/alt, unsupported indel, etc) — not an outage.
                    if no_data_count < 3:
                        print(f"\n  [debug] {url} -> 404 (no CADD record for this variant).")
                    break
                if resp.status_code != 200:
                    api_failed = True
                    print(f"\n  [debug] {url} -> {resp.status_code}. Body: {resp.text[:200]!r}")
                    break
                data = resp.json()
                if not data:
                    if no_data_count < 3:
                        print(f"\n  [debug] {url} -> 200 but empty list (CADD has no score for this exact ref/alt).")
                    break
                # Single-SNV endpoint returns [{"Chrom":.., "Ref":.., "Alt":.., "PHRED":..}]
                # — a list of ONE dict, not a list-of-lists like the range endpoint.
                raw = data[0].get("PHRED") if isinstance(data[0], dict) else None
                score = float(raw) if raw is not None else None
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                api_failed = True
                time.sleep(min(20, 2 ** attempt * 2))
            except Exception as e:
                api_failed = True
                print(f"  Warning: CADD fetch failed for {key}: {e}")
                break

        results[key] = score  # None if genuinely unresolvable — never faked

        if score is not None:
            consecutive_api_failures = 0
            new_fetches += 1
            time.sleep(1.0)   # respect rate limit
            continue

        if api_failed:
            consecutive_api_failures += 1
            if consecutive_api_failures >= 15:
                print("\n" + "!" * 60)
                print(f"CADD API had {consecutive_api_failures} genuine transport/rate-limit")
                print("failures in a row (timeouts, 5xx, or exhausted 429 retries).")
                print("Stopping instead of continuing to hammer it. Already-fetched")
                print("scores are cached — re-run later to pick up where this left off.")
                print("!" * 60)
                break
        else:
            # A clean "no data" answer (404 or empty 200) — not an API failure,
            # doesn't reset or advance the failure streak, doesn't abort the run.
            no_data_count += 1

    # Save updated cache
    with open(CADD_CACHE, "w") as f:
        json.dump(results, f)

    print(f"  Fetched {new_fetches} new scores ({no_data_count} confirmed 'no CADD record'). "
          f"Total cache: {len(results)}.")
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
        help="all/clinvar/1kg download source files; cadd/gnomad do not fetch "
             "here (use src/data/build_features.py)"
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

    print("\nCADD and gnomAD features: python src/data/build_features.py")
    print("MalariaGEN Pf7 is not used by this human-variant pipeline; no manual Pf7 step is required.")
    print("Source paths, caches, and limitations: docs/DATA.md")
    print("\nAll done.")


if __name__ == "__main__":
    main()
