# West African Variant Screener

A research prototype that scores manually supplied genetic-variant annotations
using a ClinVar-trained classifier and African population-frequency features.
The interface covers HBB, G6PD, ACKR1 (API key `DARC`), HBA1 and HBA2,
with gene reference loci, protein structures and optional ESM2 substitution maps.

**Research use only. Not validated for clinical use.** A model score is not a
diagnosis or a clinical variant classification. Real-data provenance and
deployment health do not establish clinical validity or West African population
performance. Reports from use in clinics have not yet been incorporated into
the results below.

Documentation reviewed against the repository on **30 October 2026**. This is a
documentation update, not a new training run or a live-server verification.

## Documentation

| Guide | Contents |
| --- | --- |
| [Using the screener](docs/USAGE.md) | Current controls, interpretation, troubleshooting and feedback to record |
| [API reference](docs/API.md) | Endpoints, input ranges, responses and model states |
| [Deployment](docs/DEPLOYMENT.md) | Docker, systemd, Nginx/HTTPS, artifact updates and historical AWS deployment records |
| [Data and training](docs/DATA.md) | Downloads, feature construction, caches, provenance and limitations |
| [Gene reference](docs/GENE_REFERENCE.md) | GRCh38 coordinates, ACKR1/DARC mapping and structures |
| [Substitution maps](docs/HEATMAPS.md) | Optional ESM2 precomputation, JSON format and serving |

## Run locally

Run commands from the repository root. Python 3.11 matches the serving
container. The HTML/CSS/JavaScript frontend has **no Node/npm build step**;
FastAPI serves it directly.

```bash
git clone https://github.com/Trixx4191/malaria-sickle-screener.git
cd malaria-sickle-screener
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-runtime.txt
python -m uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. API documentation is at `/docs` and `/redoc`;
the schema is at `/openapi.json`. No `.env` file, API key or external data
download is required to start a local demonstration.

`data/` and `outputs/` are gitignored. A clean clone has no trained artifact:
without `REQUIRE_REAL_MODEL`, a missing artifact causes the service to fit an
800-example synthetic demonstration model in memory. The UI labels it as
synthetic and withholds test AUC. A present but unreadable or incompatible
artifact causes startup to fail; it does not fall back to a demonstration.

To serve an existing research model, obtain the trusted matching artifact and
its metadata from the project maintainer and place them at:

```text
outputs/models/variant_screener_v1.pkl
outputs/models/model_meta.json
```

The bundle contains the estimator, feature order, provenance and evaluation
metadata. Install the matching scikit-learn version (currently pinned to
`1.9.0`) and start in strict mode:

```bash
REQUIRE_REAL_MODEL=true MODEL_N_JOBS=1 python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

Strict mode requires a compatible bundle marked `data_provenance: "real"`.
Restart after replacing a bundle: models load at process startup.
See [deployment](docs/DEPLOYMENT.md) for artifact transfer and production setup.

## Current interface

Select a gene, set its region and three numerical annotations, then select
**Score variant**. Changing an annotation clears the previous result until
rescored. The four presets immediately score illustrative feature values;
they do not fetch or identify specific variants.

The gene strip displays Ensembl 116 / GRCh38 gene spans. The structure panel
loads `2HHB` for the globins, `2BH9` for G6PD and an AlphaFold model for
ACKR1/DARC. **Residue**, **Focus**, **Reset** and **PDB file** control the viewer.
Residue selection, gene coordinates and structure data do not enter the
classifier. Predictions continue if external structure services are unavailable.

Results show the model percentage, a tier, rule-based notes and expandable
heuristic feature weights. These weights are not per-prediction SHAP values.
The optional **Amino acid substitutions** panel appears only when a gene's
precomputed JSON is available; [generate maps separately](docs/HEATMAPS.md).

## Recorded model results

The local model metadata records the corrected **24 October 2026** training
run, using **1,805** real-feature variants built on 16 July 2026. These are
computational evaluation results, not outcomes from clinic users.

| Metadata field | Recorded value |
| --- | --- |
| Saved model | Random Forest, 200 trees, maximum depth 10 |
| Training / held-out test variants | 1,444 / 361 |
| Held-out test AUC-ROC | 0.9825 |
| Five-fold training CV AUC | 0.9700 ± 0.0052 |
| CV method | Stratified training folds; SMOTE fitted within each fold |
| Held-out AFR-frequency subset (`allele_freq_afr > 0.01`) | 6 variants, all benign; AUC unavailable |

The recorded feature matrix contains HBB (1,050), G6PD (523), HBA2 (130) and
HBA1 (102): 1,199 benign and 606 pathogenic variants before oversampling.
DARC is selectable in the app but has no variants in this recorded matrix.
The earlier AFR-subset AUC of 1.000 and cross-validation that resampled before
fold splitting are withdrawn. The frequency subset is not an independently
validated West African cohort. Inspect `/api/model-info` for the model actually
loaded by a running instance; a replacement artifact may report other results.

## Methods

1. The parser selects GRCh38 ClinVar records with exact target-gene matches
   and supported benign/likely benign or pathogenic/likely pathogenic labels.
2. Feature building queries gnomAD v4 genome AFR frequencies and CADD
   GRCh38-v1.7 scores, using local caches. The downloaded 1000 Genomes sample
   panel is reference material; it does not supply the current model frequencies.
3. The six features are `allele_freq_afr`, `cadd_score`, `gene_region`,
   `conservation_phylop`, `is_hbb` and `review_stars`. Conservation is a
   CADD-derived proxy rather than measured phyloP. At serving time,
   `review_stars` is fixed to 1 and gene identity only changes `is_hbb`.
4. A stratified 80/20 split separates training from the held-out test set.
   The forest uses fold-local SMOTE during training CV and SMOTE on the full
   training split for the final fit. Logistic regression is an optional baseline.
5. Serving returns the estimator's class-1 score and applies fixed display
   thresholds: below 40% benign, 40% to below 75% uncertain, 75% and above
   pathogenic. These are application tiers. Probability calibration and clinical
   classification criteria are not implemented.

See [data limitations](docs/DATA.md), including missing CADD rows, inferred
regions, ambiguous gnomAD zeros, cache versioning and synthetic-mode behavior.
Offline SHAP plotting is separate from web predictions and does not produce
additional held-out validation metrics.

## Rebuild the research model

Use a separate environment with the full research dependencies. Download,
feature-build and training commands can overwrite generated files and the
existing model; preserve any artifacts needed for comparison before running.

```bash
python -m pip install -r requirements.txt
python src/data/download.py --dataset all
python src/data/parse_clinvar.py
python src/data/build_features.py
python src/models/train.py --model all
```

`--dataset all` downloads ClinVar and the 1000 Genomes sample panel only;
feature building makes the per-variant gnomAD and CADD calls. The default
feature build requires remote lookups or usable cached values and drops
unresolved rows. No MalariaGEN registration is needed for this pipeline.
For the optional offline SHAP step on a forest, run
`python src/models/evaluate.py`; see its limitations in [DATA.md](docs/DATA.md).

The runner `python src/pipeline/run_pipeline.py --model all --skip-evaluate`
combines download, feature construction and training. Omit `--skip-evaluate`
to attempt the separate SHAP plotting step. Use [the data guide](docs/DATA.md)
for reuse flags and cache refreshes when changing source releases.

## Deployment and verification

The configured project URL is
[malaria-sickle-screener.13-62-14-125.sslip.io](https://malaria-sickle-screener.13-62-14-125.sslip.io).
Availability was not rechecked during this documentation review. The
[deployment guide](docs/DEPLOYMENT.md) covers the recorded Lightsail setup,
current commands and Hugging Face Docker Spaces. The Dockerfile uses port
**7860**, one Uvicorn worker and strict real-model mode.

Existing regression checks run from the repository root after installing the
full research dependencies:

```bash
python -m pip install pytest httpx
python -m pytest -q
node --test tests/test_ui.mjs

# Against an already-running real-data model (136 valid prediction requests):
python scripts/smoke_deployment.py --base-url http://127.0.0.1:8000
```

The smoke script requires a real-data model and exercises routes, validation
and prediction ranges. It intentionally fails against a synthetic demo.
Its latency figures are request timings, not a concurrent load benchmark.

## Repository layout

```text
webapp/                  FastAPI backend and served static frontend
src/data/                Downloads, ClinVar parsing and feature construction
src/models/              Training and offline explanation plots
src/pipeline/            Pipeline runner
src/utils/config.py      Paths, target genes, source URLs and model settings
src/ui/app.py            Legacy Gradio prototype; outside the current run path
scripts/                 Heatmap precompute, VM inspection and deployment smoke check
deploy/                  systemd, Nginx, certificate hook and runtime lock snapshot
docs/                    Usage, API, deployment, data and reference guides
tests/                   API, model, parser, training and frontend regression checks
data/                    Local source data, caches and heatmaps (gitignored)
outputs/                 Local models, metadata and figures (gitignored)
```

## Author and licensing

Built by **Alhassan Salifu**, Accra, Ghana.
[GitHub](https://github.com/Trixx4191) ·
[Email](mailto:trixx4191@gmail.com)

Data sources and dependencies retain their own licenses and access terms.
The repository currently has no standalone `LICENSE` file; the earlier README
reference to an included MIT license was unsupported.
