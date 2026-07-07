"""
main.py — FastAPI backend for the West Africa Variant Screener.

Run locally:
    uvicorn webapp.main:app --reload --port 8000

Deploy to Hugging Face Spaces (Docker SDK):
    See ../Dockerfile — the Space builds this image and exposes port 7860.
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .model_service import service

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="West Africa Variant Screener API")


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


app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
