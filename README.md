# West African Variant Screener

ClinVar-based variant scoring with African population annotations. This
research application connects data preparation, model evaluation and an
interactive interface for HBB, G6PD, HBA1, HBA2 and ACKR1 (`DARC` in the API).

**Research use only. Clinical performance has not been established.**

## Platform use

The platform has **500 users**. This count describes people who used the
software and is separate from the variant records used to evaluate its
classifier. See [platform use and evaluation scope](docs/USER_STUDY.md).

## Results

The saved Random Forest was evaluated on a stratified split of 1,805
ClinVar-labeled variants: 1,444 for training and 361 for testing.

| Measure | Recorded result |
| --- | --- |
| Held-out test AUC-ROC | 0.9825 |
| Binary test accuracy | 94.7% |
| Serving-compatible test AUC-ROC | 0.9652 |
| Serving-compatible binary accuracy | 94.2% |
| Five-fold training CV AUC | 0.9700 ± 0.0052 (fold standard deviation) |
| Held-out subset with AFR frequency > 0.01 | 6 variants, all benign; AUC undefined |

The first two rows use the saved model's training-time inputs. The
serving-compatible rows fix review quality to 1, as the app does. These
results describe the retained ClinVar feature dataset. They do not
measure clinical performance or the accuracy of the interface's three score
tiers. Training data cover HBB, G6PD, HBA1 and HBA2; ACKR1/DARC has reference
views but no examples in the recorded training matrix.

The [evaluation guide](docs/EVALUATION.md) describes dataset coverage,
feature limitations, the input comparison and artifact checksums.

## Research paper

[West Africa Variant Screener: Reproducible Evaluation](docs/Alhassan_Salifu_Babamu_Variant_Screener_Paper.pdf)
examines the classifier, feature ablations, stricter evaluation splits and
data coverage. It separates internal label prediction from clinical claims.

## Project scope

- **Data pipeline:** GRCh38 ClinVar filtering, gnomAD genome AFR frequencies,
  CADD scores, cached lookups and feature-provenance tracking.
- **Classifier:** a six-feature Random Forest with fold-local SMOTE during
  cross-validation, plus a logistic-regression baseline.
- **Scoring interface:** manual annotation inputs, model-state reporting,
  score tiers and heuristic feature weights.
- **Reference views:** Ensembl gene loci, PDB/AlphaFold structures and residue
  selection. Optional ESM2 substitution maps are generated separately.
- **Serving:** FastAPI with static HTML/CSS/JavaScript, artifact validation,
  a strict model-loading mode, Docker and native deployment configurations.

The application scores supplied annotations; it does not retrieve a variant
from coordinates or a residue. Gene loci, structures and ESM2 scores provide
separate reference views and do not enter the classifier.

## Methods

The parser selects GRCh38 ClinVar records with supported benign/likely benign
or pathogenic/likely pathogenic labels. Feature construction combines gnomAD
AFR frequency, CADD score, a name-derived gene region, a CADD-derived
conservation proxy, an HBB flag and ClinVar review quality.

Training uses a stratified 80/20 split with seed 42. The Random Forest has
200 trees and maximum depth 10. SMOTE is fitted within each training CV fold
and on the training split for the final fit; the test set remains held out.
The serving interface derives the HBB flag and fixes review quality to 1.
Gene identity otherwise does not distinguish the four non-HBB options.

The interface displays class-1 model output as a percentage and uses fixed
tiers: below 40%, 40% to below 75%, and 75% or above. No probability
calibration step or calibration evaluation is recorded. Feature weights are
heuristic; offline SHAP plotting is a separate script. See
[data construction](docs/DATA.md) and
[evaluation limits](docs/EVALUATION.md#limitations).

## Run locally

Run from the repository root. Python 3.11 matches the container; the frontend
needs no Node/npm build step.

```bash
git clone https://github.com/Trixx4191/malaria-sickle-screener.git
cd malaria-sickle-screener
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-runtime.txt
python -m uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. API documentation is at `/docs` and `/redoc`;
the schema is at `/openapi.json`.

Models and datasets are gitignored. A clean clone starts a labeled synthetic
demonstration when no model artifact is present. No API key or data download
is required for that mode. To serve the research model, obtain the trusted
artifact pair from the project maintainer:

```text
outputs/models/variant_screener_v1.pkl
outputs/models/model_meta.json
```

The saved model requires the matching scikit-learn version, currently pinned
to `1.9.0`. Start with strict loading to require a compatible real-provenance
bundle:

```bash
REQUIRE_REAL_MODEL=true MODEL_N_JOBS=1 python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

A present but incompatible artifact fails startup. Restart the app after
replacing a model, then check `/api/health` and `/api/model-info`.

## Rebuild the research model

Use a research environment with the full dependencies. These commands
overwrite generated data and model files; retain the previous artifacts if
needed for comparison.

```bash
python -m pip install -r requirements.txt
python src/data/download.py --dataset all
python src/data/parse_clinvar.py
python src/data/build_features.py
python src/models/train.py --model all
```

The downloader retrieves ClinVar and the 1000 Genomes sample panel.
Feature construction queries gnomAD and CADD; the panel is reference material.
Live source updates may produce a different dataset and evaluation. See
[DATA.md](docs/DATA.md) for cache handling, synthetic checks, the pipeline
runner and optional offline explanation plots.

## Deployment and checks

[Configured screener URL](https://malaria-sickle-screener.13-62-14-125.sslip.io)
· [Deployment guide](docs/DEPLOYMENT.md)

The Dockerfile uses port 7860, one Uvicorn worker and strict model loading.
Check the public page, `/api/health` and `/api/model-info` after deployment.
The [deployment guide](docs/DEPLOYMENT.md#verification) explains the checks.

After installing research dependencies, run the existing checks:

```bash
python -m pip install pytest httpx
python -m pytest -q
node --test tests/test_ui.mjs

# Against an already-running real-data model:
python scripts/smoke_deployment.py --base-url http://127.0.0.1:8000
```

The smoke script checks 136 valid predictions, 19 invalid requests and the
API/static routes. It requires real provenance and is separate from model
accuracy evaluation. Browser-side structures also require WebGL and external
downloads; prediction does not depend on the viewer.

## Guides

| Guide | Contents |
| --- | --- |
| [Platform use](docs/USER_STUDY.md) | User count, evaluation denominators and evidence scope |
| [Evaluation](docs/EVALUATION.md) | Recorded results, dataset coverage, limitations and evidence files |
| [Usage](docs/USAGE.md) | Controls, outputs, interpretation and troubleshooting |
| [API](docs/API.md) | Routes, inputs, responses and model states |
| [Data](docs/DATA.md) | Sources, feature construction, caches and training |
| [Gene reference](docs/GENE_REFERENCE.md) | GRCh38 loci, ACKR1/DARC mapping and protein records |
| [Heatmaps](docs/HEATMAPS.md) | Optional ESM2 generation, format and serving |
| [Deployment](docs/DEPLOYMENT.md) | Artifact transfer, Docker, systemd, HTTPS and updates |

## Repository layout

```text
webapp/                  FastAPI backend and served frontend
src/data/                Downloads, parsing and feature construction
src/models/              Training and offline explanation plots
src/pipeline/            Pipeline runner
src/utils/config.py      Paths, source URLs and model settings
src/ui/app.py            Retained Gradio prototype; outside the serving path
scripts/                 Heatmap generation, VM inspection and smoke checks
deploy/                  Runtime, systemd and Nginx configurations
docs/                    Research and operational documentation
tests/                   API, model, parser, training and frontend checks
data/                    Local data, caches and heatmaps (gitignored)
outputs/                 Local artifacts and figures (gitignored)
```

## Author and licensing

**Alhassan Salifu Babamu**, Ghana.
[GitHub](https://github.com/Trixx4191) · [Email](mailto:trixx4191@gmail.com)

Data and dependencies retain their providers' licenses and terms. A
standalone source-code license has not been included in this repository.
