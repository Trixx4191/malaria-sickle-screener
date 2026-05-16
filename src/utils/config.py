"""
config.py — single source of truth for all paths, constants, and settings.
Import this everywhere instead of hardcoding paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Root paths ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA_RAW      = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_EXTERNAL  = ROOT / "data" / "external"
OUTPUTS        = ROOT / "outputs"
FIGURES        = OUTPUTS / "figures"
MODELS_DIR     = OUTPUTS / "models"

# Create dirs if they don't exist
for d in [DATA_RAW, DATA_PROCESSED, DATA_EXTERNAL, FIGURES, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── API credentials ──────────────────────────────────────────────────────────
NCBI_API_KEY  = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL    = os.getenv("NCBI_EMAIL", "")
HF_TOKEN      = os.getenv("HF_TOKEN", "")
HF_USERNAME   = os.getenv("HF_USERNAME", "")
CADD_API_BASE = os.getenv("CADD_API_BASE", "https://cadd.gs.washington.edu/api/v1.0/")
GNOMAD_API    = os.getenv("GNOMAD_API", "https://gnomad.broadinstitute.org/api")

# ─── Data source URLs ─────────────────────────────────────────────────────────
CLINVAR_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
)
KG_PANEL_URL = (
    "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/"
    "integrated_call_samples_v3.20130502.ALL.panel"
)

# ─── West African population codes (1000 Genomes) ─────────────────────────────
WEST_AFRICAN_POPS = ["YRI", "ESN", "MSL", "GWD"]   # Yoruba, Esan, Mende, Gambian
ALL_AFR_POPS      = ["YRI", "ESN", "MSL", "GWD", "LWK", "ASW", "ACB"]

# ─── Target genes ─────────────────────────────────────────────────────────────
TARGET_GENES = {
    "HBB":  {"chr": "11", "desc": "Sickle-cell / beta-thalassemia"},
    "G6PD": {"chr": "X",  "desc": "Malaria resistance"},
    "DARC": {"chr": "1",  "desc": "Duffy antigen / P. vivax resistance"},
    "HBA1": {"chr": "16", "desc": "Alpha-thalassemia"},
    "HBA2": {"chr": "16", "desc": "Alpha-thalassemia"},
}

# ─── ClinVar significance mapping ─────────────────────────────────────────────
# Map raw ClinVar strings → binary label
CLINVAR_PATHOGENIC = {
    "Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"
}
CLINVAR_BENIGN = {
    "Benign", "Likely benign", "Benign/Likely benign"
}
# Everything else (Uncertain significance, Conflicting, etc.) → drop for training

# ─── Model settings ───────────────────────────────────────────────────────────
RANDOM_SEED    = 42
TEST_SIZE      = 0.20
CV_FOLDS       = 5

RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": 10,
    "min_samples_split": 5,
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
    "class_weight": "balanced",   # backup for imbalance (SMOTE is primary)
}

# CADD score threshold — variants above this are considered likely deleterious
CADD_DELETERIOUS_THRESHOLD = 20.0

# AFR allele frequency threshold for "West African validation subset"
AFR_FREQ_THRESHOLD = 0.01   # variants with AFR freq > 1% in validation set

# ─── Output filenames ─────────────────────────────────────────────────────────
MODEL_FILE         = MODELS_DIR / "variant_screener_v1.pkl"
FEATURE_MATRIX     = DATA_PROCESSED / "features.csv"
CLINVAR_CLEAN      = DATA_PROCESSED / "clinvar_clean.csv"
KG_PANEL_FILE      = DATA_RAW / "1kg_panel.tsv"
CADD_CACHE         = DATA_EXTERNAL / "cadd_cache.json"
