"""
parse_clinvar.py — parse the ClinVar variant_summary.txt file,
filter for target genes, and produce a clean labelled DataFrame.

Output columns:
    variant_id, gene, chr, pos, ref, alt, significance, label, gene_region,
    review_stars, is_hbb

See docs/DATA.md for exact gene/label filtering and region-inference limits.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import (
    DATA_RAW, DATA_PROCESSED, TARGET_GENES,
    CLINVAR_PATHOGENIC, CLINVAR_BENIGN, CLINVAR_CLEAN
)


CLINVAR_COLS = [
    "AlleleID", "Type", "Name", "GeneID", "GeneSymbol",
    "HGNC_ID", "ClinicalSignificance", "ClinSigSimple",
    "LastEvaluated", "RS# (dbSNP)", "nsv/esv (dbVar)",
    "RCVaccession", "PhenotypeIDS", "PhenotypeList",
    "Origin", "OriginSimple", "Assembly", "ChromosomeAccession",
    "Chromosome", "Start", "Stop", "ReferenceAllele", "AlternateAllele",
    "Cytogenetic", "ReviewStatus", "NumberSubmitters",
    "Guidelines", "TestedInGTR", "OtherIDs", "SubmitterCategories",
    "VariationID", "PositionVCF", "ReferenceAlleleVCF", "AlternateAlleleVCF"
]

# Map review status → star count (0–4)
REVIEW_STAR_MAP = {
    "no assertion criteria provided": 0,
    "no assertion provided": 0,
    "criteria provided, single submitter": 1,
    "criteria provided, conflicting interpretations": 1,
    "criteria provided, multiple submitters, no conflicts": 2,
    "reviewed by expert panel": 3,
    "practice guideline": 4,
}


def load_clinvar(path: Path = None) -> pd.DataFrame:
    path = path or (DATA_RAW / "variant_summary.txt")
    if not path.exists():
        raise FileNotFoundError(
            f"ClinVar file not found at {path}.\n"
            "Run: python src/data/download.py --dataset clinvar"
        )
    print(f"Loading ClinVar from {path} …")

    expected_cols = [
        "VariationID", "GeneSymbol", "Assembly", "ClinicalSignificance",
        "Name", "ReviewStatus", "Chromosome", "PositionVCF",
        "ReferenceAlleleVCF", "AlternateAlleleVCF"
    ]

    rows = []
    for chunk in pd.read_csv(
        path,
        sep="\t",
        low_memory=False,
        on_bad_lines="skip",
        encoding="utf-8",
        usecols=expected_cols,
        chunksize=200_000,
    ):
        rows.append(chunk)

    if not rows:
        return pd.DataFrame(columns=expected_cols)

    df = pd.concat(rows, ignore_index=True)
    print(f"  Loaded {len(df):,} total variants.")
    return df


def filter_target_genes(df: pd.DataFrame) -> pd.DataFrame:
    genes = list(TARGET_GENES.keys())
    df = df.copy()
    df["GeneSymbol"] = df["GeneSymbol"].astype(str).str.strip()
    filtered = df[df["GeneSymbol"].isin(genes)].copy()
    print(f"  After gene filter ({genes}): {len(filtered):,} variants.")
    return filtered


def filter_grch38(df: pd.DataFrame) -> pd.DataFrame:
    """Keep entries in the GRCh38 assembly used by this pipeline."""
    df = df.copy()
    df["Assembly"] = df["Assembly"].fillna("").astype(str).str.strip()
    filtered = df[df["Assembly"] == "GRCh38"].copy()
    print(f"  After GRCh38 filter: {len(filtered):,} variants.")
    return filtered


def assign_label(sig: str) -> int | None:
    """Return 1 (pathogenic), 0 (benign), or None (drop)."""
    if pd.isna(sig):
        return None
    sig_clean = sig.strip()
    if sig_clean in CLINVAR_PATHOGENIC:
        return 1
    if sig_clean in CLINVAR_BENIGN:
        return 0
    return None   # Uncertain, Conflicting → drop


def infer_gene_region(name: str) -> int:
    """
    Rough gene-region classifier from variant name string.
    Returns: 2=exonic, 1=UTR, 0=intronic/other
    """
    if pd.isna(name):
        return 0
    name_lower = name.lower()
    if any(t in name_lower for t in ["p.", "c.", "missense", "nonsense", "frameshift", "stop"]):
        return 2   # exonic
    if "utr" in name_lower:
        return 1
    return 0   # intronic / intergenic


def parse(save: bool = True) -> pd.DataFrame:
    df = load_clinvar()
    df = filter_target_genes(df)
    df = filter_grch38(df)

    # Assign binary labels
    df["ClinicalSignificance"] = df["ClinicalSignificance"].fillna("").astype(str)
    df["label"] = df["ClinicalSignificance"].map(assign_label)
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    print(f"  After removing uncertain significance: {len(df):,} variants.")
    print(f"  Label distribution:\n{df['label'].value_counts().to_string()}")

    # Gene-region feature
    df["gene_region"] = df["Name"].map(infer_gene_region)

    # Review star rating (proxy for evidence quality)
    df["review_stars"] = (
        df["ReviewStatus"].str.lower().map(REVIEW_STAR_MAP).fillna(0).astype(int)
    )

    # Is-HBB binary flag
    df["is_hbb"] = (df["GeneSymbol"] == "HBB").astype(int)

    # Clean output
    out = df[[
        "VariationID", "GeneSymbol", "Chromosome", "PositionVCF",
        "ReferenceAlleleVCF", "AlternateAlleleVCF",
        "ClinicalSignificance", "label", "gene_region", "review_stars", "is_hbb"
    ]].rename(columns={
        "VariationID": "variant_id",
        "GeneSymbol": "gene",
        "Chromosome": "chr",
        "PositionVCF": "pos",
        "ReferenceAlleleVCF": "ref",
        "AlternateAlleleVCF": "alt",
        "ClinicalSignificance": "significance",
    }).reset_index(drop=True)

    if save:
        CLINVAR_CLEAN.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(CLINVAR_CLEAN, index=False)
        print(f"\n  Saved to: {CLINVAR_CLEAN}")

    return out


if __name__ == "__main__":
    result = parse()
    print(result.head(10).to_string())
