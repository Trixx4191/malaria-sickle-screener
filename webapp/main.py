"""
main.py — FastAPI backend for the West Africa Variant Screener web UI.

Run:
    uvicorn webapp.main:app --reload --port 8000
    open http://localhost:8000
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp.model_service import ModelService

ROOT = Path(__file__).resolve().parents[1]
HEATMAPS_DIR = ROOT / "data" / "heatmaps"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="West Africa Variant Screener")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

service = ModelService()


class PredictRequest(BaseModel):
    allele_freq_afr: float = Field(ge=0.0, le=1.0)
    cadd_score: float = Field(ge=0.0, le=60.0)
    gene_region: str  # "exonic" | "utr" | "intronic"
    conservation_phylop: float = Field(ge=-5.0, le=5.0)
    gene_name: str


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
    path = HEATMAPS_DIR / f"{gene.strip().upper()}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Heatmap not precomputed for this gene yet")
    with open(path) as f:
        return json.load(f)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
