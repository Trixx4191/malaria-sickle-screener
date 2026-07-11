"""
main.py — FastAPI backend for the West Africa Variant Screener.

Run locally:
    uvicorn webapp.main:app --reload --port 8000

Deploy to Hugging Face Spaces (Docker SDK):
    See ../Dockerfile — the Space builds this image and exposes port 7860.
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel, Field

from .model_service import service


HEATMAP_DIR = Path(__file__).resolve().parent.parent / "data" / "heatmaps"

app = FastAPI(title="West Africa Variant Screener API")


# Reference metadata for the genes this tool covers. `structures` lists real
# deposited PDB entries where one exists; `alphafold_uniprot` is used as a
# fallback (clearly labeled as a predicted model, not an experimental one)
# for targets with no experimental structure, e.g. DARC/ACKR1 (a GPCR).
GENE_REGISTRY = {
    "HBB": {
        "uniprot": "P68871",
        "structures": [
            {"id": "2HHB", "chain": "B", "label": "2HHB — deoxyhemoglobin (T state)"},
            {"id": "1HHO", "chain": "B", "label": "1HHO — oxyhemoglobin (R state)"},
        ],
    },
    "HBA1": {
        "uniprot": "P69905",
        "structures": [
            {"id": "2HHB", "chain": "A", "label": "2HHB — deoxyhemoglobin (T state)"},
            {"id": "1HHO", "chain": "A", "label": "1HHO — oxyhemoglobin (R state)"},
        ],
    },
    "HBA2": {
        "uniprot": "P69905",
        "structures": [
            {"id": "2HHB", "chain": "C", "label": "2HHB — deoxyhemoglobin (T state)"},
            {"id": "1HHO", "chain": "C", "label": "1HHO — oxyhemoglobin (R state)"},
        ],
    },
    "G6PD": {
        "uniprot": "P11413",
        "structures": [
            {"id": "2BH9", "chain": "A", "label": "2BH9 — human G6PD dimer"},
        ],
    },
    "DARC": {
        "uniprot": "Q16570",
        "structures": [],
        "alphafold_uniprot": "Q16570",
    },
}


class VariantInput(BaseModel):
    allele_freq_afr: float = Field(ge=0.0, le=1.0)
    cadd_score: float = Field(ge=0.0, le=60.0)
    gene_region: Literal["Exonic (coding)", "UTR (untranslated)", "Intronic / other"]
    conservation_phylop: float = Field(ge=-3.0, le=3.0)
    gene_name: str = "HBB"


@app.get("/api/model-info")
def model_info():
    return service.info()


@app.post("/api/predict")
def predict(payload: VariantInput):
    return service.predict(
        allele_freq_afr=payload.allele_freq_afr,
        cadd_score=payload.cadd_score,
        gene_region=payload.gene_region,
        conservation_phylop=payload.conservation_phylop,
        gene_name=payload.gene_name,
    )


@app.get("/api/gene-registry")
def gene_registry():
    """Known genes with UniProt accession + available real/AlphaFold structures."""
    return GENE_REGISTRY


@app.get("/api/heatmap/{gene}")
def heatmap(gene: str):
    """
    Serve a precomputed per-position x per-substitution effect matrix
    (ESM2 zero-shot masked-marginal scores — see scripts/compute_heatmap.py).

    Returns 404 if the gene has no cached heatmap yet; the frontend treats
    that as "no matrix available" and hides the panel rather than faking data.
    """
    path = HEATMAP_DIR / f"{gene.upper()}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No heatmap cached for gene '{gene}'. Run scripts/compute_heatmap.py first.")
    import json
    return json.loads(path.read_text())





if __name__ == "__main__":

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
