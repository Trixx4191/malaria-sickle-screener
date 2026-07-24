# West Africa Variant Screener

**AI classifier predicting pathogenic genetic variants in West African populations, with focus on malaria-resistance and sickle-cell (HBB) genes.**

Built by a high school researcher in Accra, Ghana. Inspired by Harvard's [popEVE](https://www.nature.com/articles/s41588-025-02400-1) model — but optimized for West African genomic data, which is systematically underrepresented in existing tools.

---

## Key Results

*Last verified: real-data pipeline run of 2026-07-16 — 1,805 variants (of 2,177 ClinVar
labels) with real gnomAD AFR frequencies and real CADD scores. See
[`RELEASE_NOTES.md`](RELEASE_NOTES.md) for exactly what "real" required fixing.*

| Model | AUC-ROC | Accuracy | Notes |
|---|---|---|---|
| Logistic Regression (baseline) | 0.954 | 0.94 | n=361 held-out test set |
| **Random Forest + SMOTE (best)** | **0.983** | **0.95** | n=361 held-out test set |
| Random Forest, 5-fold CV | 0.980 ± 0.003 | — | mean ± std across folds |

Test-set performance by class (Random Forest):

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Benign | 0.97 | 0.95 | 0.96 | 240 |
| Pathogenic | 0.90 | 0.94 | 0.92 | 121 |

**Training data**: 1,805 variants — HBB (1,050), G6PD (523), HBA2 (130), HBA1 (102).
1,199 benign / 606 pathogenic before SMOTE balancing.

> ⚠ **Open question, not yet a claimed result**: a separate AFR-allele-frequency
> subset evaluation (n=40) returned AUC-ROC = 1.000. A perfect score on a subset
> that small is more often a sign of leakage or an easy split than a genuinely
> perfect classifier, and hasn't been verified as a properly held-out,
> class-balanced subset yet. **Do not cite this number in a paper or submission
> until it's checked** — see Known Issues below.

---

## Live Demo

**[huggingface.co/spaces/trixx4191/variant-screener](#)** ←will  deploy here after Phase 4 of dev 

---

## Web app — brutalist requisition UI + live structure + substitution matrix

The web UI is a single FastAPI backend (`webapp/main.py`, `webapp/model_service.py`)
serving a plain HTML/CSS/JS frontend (`webapp/static/`).
build step, everything renders straight
from static files. Layout is four numbered panels:

- **01 / INPUT + 02 / RESULT** (left column): the variant requisition form
  (gene, region, allele frequency, CADD, conservation, optional residue
  number) and the pathogenicity call — a rubber-stamp-style tier badge
  (green / amber / red), probability bar, interpretation notes, and
  SHAP-style feature-contribution bars.
- **03 / SUBSTITUTION MATRIX** (center, popEVE-style): a per-position ×
  per-amino-acid heatmap of ESM2 zero-shot mutation-effect scores
  (masked-marginal log-odds vs. WT — the same class of signal as EVE/popEVE,
  computed from a protein language model instead of a per-protein MSA/VAE).
  Click a column to list all 20 substitutions at that position, sorted by
  effect, in the table below. **This panel only appears once real data has
  been precomputed for that gene** — see `scripts/compute_heatmap.py` and
  `data/heatmaps/README.md`. It stays hidden rather than showing placeholder
  numbers.
- **04 / STRUCTURE** (right): a real `3Dmol.js` molecular viewer —
  `2HHB` for HBB/HBA1/HBA2, `2BH9` for G6PD, an AlphaFold model for DARC
  (clearly labeled as predicted, not experimental). Enter a residue number
  (or click an example chip) to highlight the exact mutated residue —
  stick+sphere in yellow with a floating label, camera zoomed in — while the
  rest of the chain still recolors to match the pathogenicity tier once a
  prediction comes back. The four built-in example chips point at real,
  textbook-documented positions (HbS/HbC at β-globin codon 6, G6PD A- at
  residue 68, G6PD Mediterranean at residue 188), not invented coordinates.
  Download (saves the loaded PDB file), Zoom to Residue, and Reset View
  buttons included. Rotation is manual drag-only — no auto-orbiting camera,
  no particles/bloom.
- **Status bar** (top right) reports the model's real data provenance, not
  just whether a model file exists — it distinguishes three states:
  - 🟢 `✓ real data · model: ... · AUC ... · n=...` — a model trained on
    real gnomAD/CADD features. This is the only state that should be cited
    anywhere.
  - 🔴 `⚠ REAL MODEL, PLACEHOLDER DATA` — a real trained model whose
    features were zero-filled placeholders, not real API data. This state
    exists specifically so a placeholder-trained model can never silently
    look like a real result.
  - 🔴 `⚠ DEMO MODE` — no trained model exists yet at all; the app trained a
    tiny synthetic fallback on startup so the UI is still fully interactive.

### Run it

```bash
pip install -r requirements.txt
uvicorn webapp.main:app --reload --port 8000
# open http://localhost:8000
```

### Generate the substitution matrix (optional)

The "03 / SUBSTITUTION MATRIX" panel needs a one-time precompute per gene —
it needs internet access to `rest.uniprot.org` and `huggingface.co`, so it's
meant to be run on your own machine, not inside a restricted sandbox:

```bash
pip install -r scripts/requirements-heatmap.txt
python scripts/compute_heatmap.py --gene HBB
# or for every gene the app knows about:
python scripts/compute_heatmap.py --all
```

### Deploy to Hugging Face Spaces (Docker SDK)

1. Create a new Space → SDK: **Docker**
2. Push this repo (the `Dockerfile` at the repo root builds it automatically)
3. The Space exposes the app on port 7860

Once the real training pipeline has been run (`build_features.py` → `train.py`),
the same UI automatically picks up the real model — no code changes needed.

---


## The Problem

Most variant pathogenicity classifiers (ClinVar, CADD, SIFT) are trained predominantly on European cohorts. When applied to West African populations — where sickle-cell trait frequency is 10–40% and malaria-resistance variants are common — they underperform. A community health worker in Accra using these tools gets less reliable predictions than a clinician in London using the same tool.

This project builds a classifier that explicitly incorporates West African population genetics.

---

## Project Structure

```
malaria-sickle-screener/
│
├── data/
│   ├── raw/                  # Downloaded source files (gitignored, see DATA.md)
│   ├── processed/            # Cleaned feature matrices
│   ├── external/             # Reference files (gene annotations, etc.)
│   └── heatmaps/             # Precomputed ESM2 substitution matrices (see below), empty by default
│
├── scripts/
│   ├── compute_heatmap.py         # Generates data/heatmaps/<GENE>.json (run locally, needs internet)
│   └── requirements-heatmap.txt   # torch/transformers, only needed for the script above
│
├── src/
│   ├── data/
│   │   ├── download.py       # Automated data download scripts
│   │   ├── parse_clinvar.py  # ClinVar VCF parser
│   │   ├── parse_1kg.py      # 1000 Genomes panel parser
│   │   └── build_features.py # Feature matrix construction
│   ├── models/
│   │   ├── train.py          # Model training pipeline
│   │   ├── evaluate.py       # Evaluation metrics + SHAP
│   │   └── predict.py        # Inference on new variants
│   └── utils/
│       ├── config.py         # Paths, constants, settings
│       └── logger.py         # Logging setup
│
├── webapp/
│   ├── main.py                # FastAPI app: /api/model-info, /api/predict, static mount
│   ├── model_service.py       # Model loading, prediction, SHAP explanations
│   └── static/                # Plain HTML/CSS/JS frontend (index.html, style.css, script.js)
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_training.ipynb
│   └── 04_results_visualization.ipynb
│
├── tests/
│   ├── test_parser.py
│   ├── test_features.py
│   └── test_model.py
│
├── outputs/
│   ├── figures/              # SHAP plots, ROC curves, confusion matrices
│   └── models/               # Saved model files (.pkl)
│
├── docs/
│   └── PROJECT_LOG.md        # Obsidian research log (also in vault)
│
├── requirements.txt
├── setup.py
├── .env.example              # API keys template
├── .gitignore
└── README.md
```

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/Trixx4191/malaria-sickle-screener.git
cd malaria-sickle-screener
pip install -r requirements.txt
```

### 2. Set up credentials

```bash
cp .env.example .env
# Edit .env with your API keys (see SETUP.md for instructions)
```

### 3. Download the data

```bash
python src/data/download.py --dataset all
# This fetches: ClinVar, 1000 Genomes panel, CADD scores
# MalariaGEN requires manual registration (see docs/DATA.md)
```

### 4. Build the feature matrix

```bash
python src/data/build_features.py
```

### 5. Train the model

```bash
python src/models/train.py --model random_forest
```

### 6. Run the web UI

```bash
uvicorn webapp.main:app --reload --port 8000
# open http://localhost:8000
```

---

## Data Sources

| Dataset | What it provides | Access | Size |
|---|---|---|---|
| ClinVar | Pathogenicity labels | Free, no key | ~800 MB |
| 1000 Genomes Project | AFR allele frequencies | Free, no key | ~2 GB (subset) |
| CADD scores | Deleteriousness scores | Free, no key | ~80 GB (use API) |
| MalariaGEN Pf7 | Ghana malaria genomics | Free registration | ~5 GB |
| gnomAD v4 | Population frequencies | Free API | API only |

See `docs/DATA.md` for download instructions for each.

---

## API Keys Required

| Service | Purpose | How to get | Cost |
|---|---|---|---|
| NCBI E-utilities | ClinVar programmatic download | Register at ncbi.nlm.nih.gov/account | Free |
| gnomAD GraphQL | Population frequency queries | No key needed (public API) | Free |
| MalariaGEN | Pf7 dataset access | Register at malariagen.net/data | Free |
| Hugging Face | Deploy the FastAPI app (Docker SDK) | hf.co/join | Free |

No paid APIs required. Total cost: $0.

---

## Data Provenance & Known Issues

Real gnomAD/CADD data is the default, enforced behavior of this pipeline, not
an opt-in — `build_features.py` refuses to build a placeholder-only matrix
unless you explicitly pass `--allow-fake`, and every matrix it produces is
stamped with a `data_provenance` field (`real` / `synthetic_placeholder`)
that flows through training into `model_meta.json` and the web UI's status
bar. See `RELEASE_NOTES.md` for the full history of what that took to get
right — several rounds of it were silent zero-fill bugs, not obvious errors.

**Known issues, open as of the last real-data run:**

- **AFR-subset AUC = 1.000 (n=40) is unverified.** This needs a leakage check
  (is the subset properly held out from training? is n=40 just too small to
  be meaningful?) before it's cited anywhere. Currently in the results table
  above as a flagged, unverified caveat — not a claimed finding.
- **372 of 2,177 ClinVar variants (17%) have no CADD score** and are dropped
  from the training matrix rather than faked. Most are large deletions or
  malformed `ref==alt` self-substitution rows (a ClinVar/parsing artifact
  worth investigating in `parse_clinvar.py`, not yet root-caused).
- **`conservation_phylop` is a CADD-derived proxy**, not real UCSC phyloP —
  documented intentionally in `docs/DATA.md`, not a bug, but worth real
  phyloP if you want a cleaner feature set.
- **DARC has no experimental structure** — the structure panel uses an
  AlphaFold-predicted model, clearly labeled as such in the UI.

---

## Methods

1. **Variant features**: allele frequency in AFR populations (1000 Genomes), CADD deleteriousness score, gene region (exonic/intronic/UTR), conservation score (phyloP), HBB gene flag
2. **Labels**: ClinVar clinical significance — pathogenic/likely pathogenic = 1, benign/likely benign = 0
3. **Class imbalance**: SMOTE oversampling (pathogenic variants are rare)
4. **Model**: Random Forest (200 trees, max_depth=10), compared against Logistic Regression baseline
5. **Explainability**: SHAP TreeExplainer — feature importance per prediction
6. **West Africa validation**: separate evaluation on variants with AFR allele frequency > 0.01

---

## Competition Submissions

- [ ] Regeneron ISEF — Computational Biology & Bioinformatics track
- [ ] Conrad Challenge — Health & Nutrition track
- [ ] Journal of Emerging Investigators (JEI) — paper submission

---

## Faculty Connection

This project is inspired by and benchmarked against:
- **Debora Marks Lab (Harvard)** — popEVE variant effect prediction model
- **MalariaGEN Consortium** — Pf7 West African genomics data

---

## Author

**Alhassan Salifu**  |  Ghana
[trixx4191@gmail.com] | [github.com/Trixx4191]

---

## License

MIT License. Data sources retain their own licenses — see `docs/DATA.md`.
