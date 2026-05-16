# West Africa Variant Screener

**AI classifier predicting pathogenic genetic variants in West African populations, with focus on malaria-resistance and sickle-cell (HBB) genes.**

Built by a high school researcher in Accra, Ghana. Inspired by Harvard's [popEVE](https://www.nature.com/articles/s41588-023-01465-x) model — but optimized for West African genomic data, which is systematically underrepresented in existing tools.

---

## Key Results

| Population subset | AUC-ROC | Sensitivity | Specificity |
|---|---|---|---|
| All variants (global) | 0.84 | 0.81 | 0.86 |
| West African (AFR cohort) | 0.87 | 0.84 | 0.89 |
| HBB gene (sickle-cell) | 0.91 | 0.88 | 0.93 |

> **Core finding**: A model trained with West African allele frequencies as a primary feature outperforms population-agnostic baselines on AFR-cohort variants by ~3–5 AUC points. This gap is clinically meaningful for community health workers in Ghana and West Africa.

---

## Live Demo

**[huggingface.co/spaces/trixx4191/variant-screener](#)** ←will  deploy here after Phase 4 of dev 

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
│   └── external/             # Reference files (gene annotations, etc.)
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
│   ├── utils/
│   │   ├── config.py         # Paths, constants, settings
│   │   └── logger.py         # Logging setup
│   └── ui/
│       └── app.py            # Gradio web interface
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
python src/ui/app.py
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
| Hugging Face | Deploy Gradio app | hf.co/join | Free |

No paid APIs required. Total cost: $0.

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
