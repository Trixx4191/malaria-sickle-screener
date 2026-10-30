"""
main.py — FastAPI backend for the West Africa Variant Screener web UI.

Run from the repository root after installing requirements-runtime.txt:
    python -m uvicorn webapp.main:app --reload --port 8000
    open http://localhost:8000

A missing model starts a labeled synthetic demo unless REQUIRE_REAL_MODEL=true.
See README.md and docs/API.md for model states and endpoint contracts.
"""

import json
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp.model_service import ModelService
from src.utils.config import TARGET_GENES

ROOT = Path(__file__).resolve().parents[1]
HEATMAPS_DIR = ROOT / "data" / "heatmaps"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="West Africa Variant Screener")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

service = ModelService()


class PredictRequest(BaseModel):
    allele_freq_afr: float = Field(ge=0.0, le=1.0)
    cadd_score: float = Field(ge=0.0, le=60.0)
    gene_region: Literal["exonic", "utr", "intronic"]
    conservation_phylop: float = Field(ge=-5.0, le=5.0)
    gene_name: Literal["HBB", "G6PD", "DARC", "HBA1", "HBA2"]

    @field_validator("gene_name", mode="before")
    @classmethod
    def normalize_gene(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("gene_region", mode="before")
    @classmethod
    def normalize_region(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": service.demo_mode, "data_provenance": service.data_provenance}


@app.get("/api/model-info")
def model_info():
    return service.model_info()


@app.post("/api/predict")
def predict(req: PredictRequest):
    return service.predict(
        allele_freq_afr=req.allele_freq_afr,
        cadd_score=req.cadd_score,
        gene_region=req.gene_region,
        conservation_phylop=req.conservation_phylop,
        gene_name=req.gene_name,
    )


@app.get("/api/structure/{gene}")
def structure(gene: str):
    info = service.structure_for(gene)
    if info is None:
        raise HTTPException(status_code=404, detail=f"No structure registered for gene '{gene}'")
    return info


@app.get("/api/heatmap/{gene}")
def heatmap(gene: str):
    gene = gene.strip().upper()
    if gene not in TARGET_GENES:
        raise HTTPException(status_code=404, detail="Unknown gene")
    path = HEATMAPS_DIR / f"{gene}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Heatmap not precomputed for this gene yet")
    with open(path) as f:
        return json.load(f)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
