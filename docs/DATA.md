# Data sources and training pipeline

Repository behavior reviewed on 30 October 2026. Run commands from the
repository root with the research dependencies in `requirements.txt`
installed. Serving an existing model only needs `requirements-runtime.txt`;
it does not require downloads, credentials, or retraining. See the
[README](../README.md) for installation and [deployment guide](DEPLOYMENT.md)
for serving trusted artifacts.

## What the pipeline actually uses

| Source | Current role | Local file or cache |
| --- | --- | --- |
| ClinVar variant summary | GRCh38 variant coordinates, binary training labels, name-derived region, review status | `data/raw/variant_summary.txt`, `data/processed/clinvar_clean.csv` |
| gnomAD `gnomad_r4`, genome `afr` population | `allele_freq_afr` feature | `data/external/gnomad_cache.json` |
| CADD `GRCh38-v1.7` | `cadd_score` feature and conservation proxy | `data/external/cadd_cache.json` |
| 1000 Genomes sample panel | Downloadable population reference; not read by the current feature builder | `data/raw/1kg_panel.tsv` |
| Ensembl, PDB, AlphaFold, UniProt, ESM2 | Gene/structure context and optional substitution matrices; not classifier inputs | See [gene references](GENE_REFERENCE.md) and [heatmaps](HEATMAPS.md) |

MalariaGEN Pf7 and UCSC phyloP are **not inputs to the current pipeline**.
There is no patient-data import or clinic-results ingestion step. Raw data,
processed matrices, caches, model artifacts, and heatmaps are gitignored;
a clean clone does not contain them.

## Download and parse ClinVar

```bash
python src/data/download.py --dataset clinvar
python src/data/parse_clinvar.py
```

The downloader retrieves the [NCBI variant summary](https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz),
decompresses it into `data/raw/variant_summary.txt`, and removes the downloaded
`.gz`. If the decompressed file exists, it skips downloading. A manual download
must be saved and decompressed to that same path. No API key is required for
this public file. The code can append `NCBI_API_KEY` if configured, but this
is a static download, not an E-utilities request; E-utilities rate-limit
claims do not describe this download.

The parser:

- Keeps exact gene-symbol matches to `HBB`, `G6PD`, `DARC`, `HBA1`, and `HBA2`
  from `TARGET_GENES` in `src/utils/config.py`, then keeps GRCh38 rows.
- Assigns label `1` to `Pathogenic`, `Likely pathogenic`, or
  `Pathogenic/Likely pathogenic`; label `0` to `Benign`, `Likely benign`, or
  `Benign/Likely benign`. Other significance strings are dropped.
- Infers the numeric gene region from the variant name: `2` for names
  containing `p.`, `c.`, `missense`, `nonsense`, `frameshift`, or `stop`; `1`
  for remaining names containing `utr`; otherwise `0`. This is a text
  heuristic, not transcript-aware annotation.
- Maps recognized ClinVar review statuses to `review_stars` from 0 to 4,
  with unrecognized/missing statuses assigned 0, and derives `is_hbb`.

The API uses `DARC` for the gene displayed as ACKR1. The parser does not
translate `ACKR1` to `DARC`, so a source row named `ACKR1` fails its exact
gene filter. The recorded training matrix has no DARC/ACKR1 variants; the
UI's gene list does not establish training coverage.

`build_features.py` reuses `clinvar_clean.csv` if present. After intentionally
updating the raw source, rerun the parser before building features. Archive
the existing source, processed data, caches, and model first if you need to
retain the previous experiment. Source URLs are mutable; downloading again
does not recreate the historical dataset automatically.

## Build real features

```bash
python src/data/build_features.py
```

If the cleaned ClinVar CSV is absent, this command runs the parser itself.
It queries gnomAD and then CADD for the variant IDs, reuses local caches, and
writes `data/processed/features.csv` plus `features_provenance.json`.

The gnomAD query posts to `https://gnomad.broadinstitute.org/api` using
`variantId` in `chr-pos-ref-alt` format, dataset `gnomad_r4`, and
`genome { populations { id ac an } }`. It takes `ac / an` from the `afr`
population, rounded to six decimal places. It does not query exome frequencies
or select individual West African populations. The reference gene spans in
the UI are not variant coordinates and cannot be used as lookup positions.

CADD requests use this form, including the assembly/version segment:

```text
https://cadd.gs.washington.edu/api/v1.0/GRCh38-v1.7/<chr>:<pos>_<ref>_<alt>
```

The code reads the returned `PHRED` score. The [official CADD API documentation](https://cadd.bihealth.org/api)
describes the versioned path and notes that an unavailable reference/alternate
combination can return an empty list. The current client treats empty results
or 404s as no available score. It retries rate limits and transport errors;
both source clients stop their loops after repeated failures. Cached successful
lookups reduce work on the next run. CADD null entries are retried; new failed
gnomAD requests are not added to its cache.

Rows with unresolved CADD scores, unresolved gnomAD requests represented as
`None`, or missing labels are dropped. A drop rate above 30% produces a
warning; it does not abort saving the matrix. Inspect the counts and saved
provenance before training.

There is an important gnomAD limitation: an HTTP-success response with no
variant, no genome data, no `afr` entry, or an allele denominator of zero is
currently converted to `0.0`. GraphQL errors returned inside an HTTP 200
response are not explicitly rejected. Consequently, a stored zero is not
proof of an observed zero allele frequency, and `data_provenance=real` is not
a guarantee that every input has complete source coverage. Existing caches
should be audited when investigating those cases.

Both cache formats use `chr-pos-ref-alt` keys without including the source
release or assembly. Preserve them for reproducibility, but do not reuse
them blindly after changing assembly, CADD version, or gnomAD dataset. The
gnomAD dataset identifier is currently hardcoded in the fetcher; changing
`GNOMAD_API` alone does not change it.

### Feature columns

The matrix contains identifiers `variant_id`, `gene`, these six model
features in order, and the target `label`:

| Feature | Training construction | Serving behavior |
| --- | --- | --- |
| `allele_freq_afr` | gnomAD genome `afr` frequency, subject to the missing-data limitation above | Supplied manually by the caller |
| `cadd_score` | CADD PHRED score | Supplied manually |
| `gene_region` | Name-derived `exonic=2`, `utr=1`, `intronic/other=0` | Supplied region mapped to the same numeric codes |
| `conservation_phylop` | `(cadd_score / 40).clip(-3, 3)` | Supplied manually; the UI labels it a phyloP proxy |
| `is_hbb` | `1` for HBB, otherwise `0` | Derived from the selected gene |
| `review_stars` | ClinVar review-status mapping | Fixed to `1`; not a user input |

Despite its column name, `conservation_phylop` does not contain measured
phyloP scores. It duplicates information derived from CADD. Supplying
independent conservation values changes the input relationship relative to
training. Apart from `is_hbb`, the model receives no gene identity feature;
changing between the other four genes with otherwise identical inputs
produces the same classifier input.

### Feature-build settings

| Setting | Default | Effect |
| --- | --- | --- |
| `FEATURE_BUILD_USE_REMOTE` | `1` | Enables real gnomAD/CADD lookups; `1`, `true`, `yes`, and `on` enable them |
| `FEATURE_BUILD_MAX_VARIANTS` | Unset | A positive integer limits the input rows sent to each fetcher; it is not random sampling. Rows left without features are dropped |
| `GNOMAD_API` | Public endpoint above | Overrides the query endpoint |
| `CADD_API_BASE` | `https://cadd.gs.washington.edu/api/v1.0/` | Overrides the base URL; retain its trailing slash |
| `CADD_VERSION` | `GRCh38-v1.7` | Selects the CADD build/version segment |

For a deliberately synthetic offline pipeline check, both the environment
setting and CLI flag are required:

```bash
FEATURE_BUILD_USE_REMOTE=0 python src/data/build_features.py --allow-fake
```

This overwrites the usual feature outputs with zero-filled allele-frequency
and CADD features, marked `synthetic_placeholder`. `--allow-fake` alone does
not disable remote fetching. With remote fetching disabled and no flag,
the builder refuses to run. Training warns about non-real provenance but
does not refuse it; production serving with `REQUIRE_REAL_MODEL=1` rejects
such an artifact. Use a separate research checkout for synthetic checks.

## Train, evaluate, and retain provenance

```bash
python src/models/train.py --model all
python src/models/evaluate.py
```

Training uses a stratified 80/20 split with seed 42. The Random Forest's
five-fold cross-validation runs on training rows, with SMOTE fitted inside
each fold. The final forest is fitted on the training split through the
same SMOTE pipeline; only the fitted classifier is saved for serving. The
logistic baseline uses a scaler fitted on training rows. `--model all`
compares both models, but saves the Random Forest when it is included,
even if the console's highest-AUC model were different.

`evaluate.py` produces offline SHAP and feature-importance figures for the
forest. It explains up to the first 500 matrix rows with a sampled background
from the matrix; this is not a separate held-out clinical evaluation. Its
tree explainer and forest-importance code are not a general evaluation path
for a logistic-only artifact. The web app's heuristic feature bars do not
use these SHAP files.

Outputs include `outputs/models/variant_screener_v1.pkl`,
`outputs/models/model_meta.json`, and evaluation figures. Provenance from
`features_provenance.json` is copied into the model bundle and metadata.
Missing provenance becomes `unknown`. The serving bundle's embedded
provenance and metadata take precedence over an independently edited
sidecar. Retraining overwrites these filenames; retain copies and source
checksums for an experiment you need to compare later. Restart the app
after replacing model artifacts.

The end-to-end alternative, from the repository root, is:

```bash
python src/pipeline/run_pipeline.py --model all
# Reuse already downloaded raw data:
python src/pipeline/run_pipeline.py --skip-download --model all
```

The runner does not expose `--allow-fake`. Its download stage defaults to
ClinVar plus the optional 1000 Genomes panel; CADD and gnomAD are fetched at
the feature stage. Individual `--skip-features`, `--skip-train`, and
`--skip-evaluate` flags reuse existing outputs, so check their provenance
before relying on them.

The recorded real-feature dataset has 1,805 variants, with 1,444 training and
361 held-out test rows. The held-out AFR-frequency subset contains only six
variants, all benign; its AUC is undefined. An AFR-frequency threshold is
not an independent West African clinical validation cohort. See the
[README](../README.md) for the persisted evaluation values and [usage
guide](USAGE.md) for interpreting app output.

## Other sources and optional assets

`python src/data/download.py --dataset 1kg` downloads the [1000 Genomes
sample panel](https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/integrated_call_samples_v3.20130502.ALL.panel).
`--dataset all` downloads it along with ClinVar; it does not download CADD
scores, gnomAD frequencies, or MalariaGEN data. Although `--dataset cadd`
and `--dataset gnomad` are accepted by the downloader's parser, those
selections do not perform a fetch. Use the feature builder for these sources.
The configured West African panel codes are YRI, ESN, MSL, and GWD; LWK is
listed separately in the broader AFR group. These panel lists do not filter
the gnomAD feature query.

MalariaGEN [Pf7 is a *Plasmodium falciparum* parasite dataset](https://www.malariagen.net/resource/34/),
with its own [data-access guide](https://malariagen.github.io/parasite-data/pf7/Data_access.html).
It is not a human HBB/GRCh38 dataset: a parasite chromosome 11 file cannot
supply human HBB variants. No registration or Pf7 file is required to run
this project's classifier. The earlier instructions to obtain a human HBB
subset from Pf7 were incorrect.

Real UCSC conservation values would require an explicit feature-pipeline
change, new provenance, retraining, and evaluation; placing a file in
`data/external/` does not enable them. Optional ESM2 matrices are generated
separately and never enter the Random Forest; see [HEATMAPS.md](HEATMAPS.md).
Source data and external models retain their providers' terms and citation
requirements.
