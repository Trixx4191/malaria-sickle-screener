# West Africa Variant Screener

**AI classifier predicting pathogenic genetic variants in West African populations, with focus on malaria-resistance and sickle-cell (HBB) genes.**

Built by a high school researcher in Accra, Ghana. Inspired by Harvard's [popEVE](https://www.nature.com/articles/s41588-025-02400-1) model — but optimized for West African genomic data, which is systematically underrepresented in existing tools.

---

## Key Results

*Last verified: corrected training run of 2026-10-24 using the 1,805 real-feature
variants built on 2026-07-16 (of 2,177 ClinVar labels). The train/test split
contains 1,444 training and 361 held-out variants.*

| Model | AUC-ROC | Accuracy | Notes |
|---|---|---|---|
| Logistic Regression (baseline) | 0.954 | 0.94 | n=361 held-out test set |
| **Random Forest + SMOTE (best)** | **0.983** | **0.95** | n=361 held-out test set |
| Random Forest, 5-fold training CV | 0.9700 ± 0.0052 | — | SMOTE fitted separately inside each training fold |

Test-set performance by class (Random Forest):

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Benign | 0.97 | 0.95 | 0.96 | 240 |
| Pathogenic | 0.90 | 0.94 | 0.92 | 121 |

**Training data**: 1,805 variants — HBB (1,050), G6PD (523), HBA2 (130), HBA1 (102).
1,199 benign / 606 pathogenic before SMOTE balancing.

> The historical AFR-frequency subset AUC = 1.000 included training rows and
> is withdrawn. The corrected held-out subset contains only 6 variants, all
> benign, so an AUC cannot be calculated. The corrected training run produced
> exactly the same held-out predictions as the previous model; its evaluation
> metadata now records the actual split and corrected cross-validation.

---

## Live Demo

**[Open the live screener](https://malaria-sickle-screener.13-62-14-125.sslip.io)**

Deployed on the existing AWS Lightsail VM with HTTPS. The project-named
hostname uses free IP-based DNS; no purchased domain is required.

---

## Web app: gene reference and variant scoring

The web UI is a single FastAPI backend (`webapp/main.py`, `webapp/model_service.py`)
serving a plain HTML/CSS/JS frontend (`webapp/static/`). There is no frontend
build step. The interface places the selected gene's GRCh38 locus above the
annotations, protein structure, and model score. A chromosome track, cytoband,
strand, and Ensembl record provide gene context. The five reference records
are documented in [GENE_REFERENCE.md](docs/GENE_REFERENCE.md); these fields do
not enter the classifier. On mobile, results follow the annotation form.

- **Variant details and prediction results**: the annotation form
  (gene, region, allele frequency, CADD, conservation), example presets,
  and the model's pathogenicity estimate — a tier badge
  (green / amber / red), probability bar, interpretation notes, and
  heuristic relative feature-weight bars. These are not per-prediction SHAP
  explanations. Feature weights expand on demand, and model evaluation
  statistics appear beneath the inputs.
- **Substitution landscape** (optional): a per-position ×
  per-amino-acid heatmap of ESM2 zero-shot mutation-effect scores
  (masked-marginal log-odds vs. WT — the same class of signal as EVE/popEVE,
  computed from a protein language model instead of a per-protein MSA/VAE).
  Click a column to list all 20 substitutions at that position, sorted by
  effect, in the table below. **This panel only appears once real data has
  been precomputed for that gene** — see `scripts/compute_heatmap.py` and
  `data/heatmaps/README.md`. It stays hidden rather than showing placeholder
  numbers.
- **Protein structure**: a real `3Dmol.js` molecular viewer —
  `2HHB` for HBB/HBA1/HBA2, `2BH9` for G6PD, an AlphaFold model for DARC
  (clearly labeled as predicted, not experimental). The structure toolbar
  provides a separate residue field. Enter a residue number
  (or click an example chip) to highlight the exact mutated residue —
  sticks and spheres in element colors with a floating label, camera zoomed
  in. The protein cartoon uses the [PyMOL secondary-structure palette](https://3dmol.org/doc/colors.ts.html):
  helices red, beta sheets yellow, and loops/coils green. The selected chain
  is opaque and other chains are faded. Predictions preserve this palette;
  risk colors appear in the result panel. An on-screen legend explains the
  colors. The four built-in chips are illustrative feature
  presets, not retrieved variant annotations or validated clinical examples.
  Their residue highlights illustrate the structures; residue identity is
  not an input to the classifier.
  Download (saves the loaded PDB file), Zoom to Residue, and Reset View
  buttons included. Rotation is manual drag-only — no auto-orbiting camera,
  no particles/bloom.
- **Model status** (top right) reports real-data, unverified-data, synthetic
  demo, or unavailable states. Only real-data models display a held-out AUC.
  The compact status preserves provenance warnings; further detail is available
  in its tooltip and prediction notes.

### Run it

```bash
pip install -r requirements-runtime.txt
uvicorn webapp.main:app --reload --port 8000
# open http://localhost:8000
```

### Generate the substitution matrix (optional)

The substitution landscape panel needs a one-time precompute per gene —
it needs internet access to `rest.uniprot.org` and `huggingface.co`, so it's
meant to be run on your own machine, not inside a restricted sandbox:

```bash
pip install -r scripts/requirements-heatmap.txt
python scripts/compute_heatmap.py --gene HBB
# or for every gene the app knows about:
python scripts/compute_heatmap.py --all
```

### Deploy to AWS or Hugging Face Spaces

See [the deployment guide](docs/DEPLOYMENT.md) for the current AWS VM
assessment, a small serving-only container, artifact transfer, and health
checks. Models and heatmaps are gitignored, so a clean clone does not contain
them. Copy trusted model artifacts into `outputs/models/` before building.
The production container refuses to start without a compatible model with
real data provenance. Viewer failures do not prevent predictions.

For Hugging Face Spaces (Docker SDK):

1. Create a new Space → SDK: **Docker**
2. Upload the source and trusted model artifacts (the root `Dockerfile` builds it)
3. The Space exposes the app on port 7860

After training or replacing artifacts, rebuild/restart the app to load the
new model. Verify `/api/health` and `/api/model-info` after deployment.

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
that flows through training into the saved model, `model_meta.json`, and the
web UI's status bar.

**Known issues, open as of the last real-data run:**

- **Historical cross-validation and AFR-subset results are withdrawn.** CV
  previously applied SMOTE before splitting into folds, and the AFR subset
  included training rows. The 24 October 2026 run recomputed CV correctly;
  its held-out AFR subset is too small and single-class for AUC. A frequency threshold
  does not itself establish a West African validation cohort.
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
