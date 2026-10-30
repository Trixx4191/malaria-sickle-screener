# Data sources and training pipeline

Run these commands from the repository root with `requirements.txt`
installed. Serving an existing model requires only `requirements-runtime.txt`;
data downloads and retraining are separate workflows. See the
[README](../README.md) for installation and [DEPLOYMENT.md](DEPLOYMENT.md)
for serving model artifacts.

## Sources

| Source | Current role | Local file or cache |
| --- | --- | --- |
| ClinVar variant summary | GRCh38 variant coordinates, binary training labels, name-derived region, review status | `data/raw/variant_summary.txt`, `data/processed/clinvar_clean.csv` |
| gnomAD `gnomad_r4`, genome `afr` population | `allele_freq_afr` feature | `data/external/gnomad_cache.json` |
| CADD `GRCh38-v1.7` | `cadd_score` feature and conservation proxy | `data/external/cadd_cache.json` |
| 1000 Genomes sample panel | Downloadable population reference; not read by the current feature builder | `data/raw/1kg_panel.tsv` |
| Ensembl, PDB, AlphaFold, UniProt, ESM2 | Gene/structure context and optional substitution matrices; not classifier inputs | See [gene references](GENE_REFERENCE.md) and [heatmaps](HEATMAPS.md) |

MalariaGEN Pf7 and UCSC phyloP are not pipeline inputs. Raw data, matrices,
caches, model artifacts and heatmaps are gitignored and absent from a clean
clone.

## Download and parse ClinVar

```bash
python src/data/download.py --dataset clinvar
python src/data/parse_clinvar.py
```

The downloader retrieves the [NCBI variant summary](https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz),
decompresses it into `data/raw/variant_summary.txt`, and removes the downloaded
`.gz`. If the decompressed file exists, it skips downloading. A manual download
must be decompressed to that same path. This public file requires no API key.

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

The API uses `DARC` for ACKR1. The parser does not translate the alias, so
source rows named `ACKR1` fail its exact gene filter. Training coverage is
reported in [EVALUATION.md](EVALUATION.md).

`build_features.py` reuses `clinvar_clean.csv` if present. After updating the
raw source, rerun the parser before building features. Preserve the previous
source files, processed data, caches and model to retain an experiment;
mutable download URLs cannot recreate a historical dataset by themselves.

## Build features

```bash
python src/data/build_features.py
```

If the cleaned ClinVar CSV is absent, this command runs the parser itself.
It queries gnomAD and then CADD for the variant IDs, reuses local caches, and
writes `data/processed/features.csv` plus `features_provenance.json`.

The gnomAD query posts to `https://gnomad.broadinstitute.org/api` using
`variantId` in `chr-pos-ref-alt` format, dataset `gnomad_r4`, and
`genome { populations { id ac an } }`. It takes `ac / an` from the `afr`
population, rounded to six decimal places. It queries neither exome frequencies
nor individual West African populations. Lookup coordinates must describe
the variant, rather than the gene span shown in the UI.

CADD requests use this form, including the assembly/version segment:

```text
https://cadd.gs.washington.edu/api/v1.0/GRCh38-v1.7/<chr>:<pos>_<ref>_<alt>
```

The client reads `PHRED` and treats an empty result or 404 as no available
score; see the [CADD API documentation](https://cadd.bihealth.org/api).
Both source clients retry rate limits and transport failures, stop after
repeated failures, and cache successful lookups. CADD null entries are
retried; new failed gnomAD requests are not cached.

Rows with unresolved CADD scores, unresolved gnomAD requests represented as
`None`, or missing labels are dropped. A drop rate above 30% produces a
warning; it does not abort saving the matrix. Inspect the counts and saved
provenance before training.

The gnomAD fetcher converts a successful response with no variant, genome
data, `afr` entry or positive allele denominator to `0.0`. It does not
explicitly reject GraphQL errors inside HTTP 200 responses. A stored zero
therefore need not represent an observed zero frequency. The `real`
provenance label records the remote-fetch branch, not complete source
coverage; review cached values and source coverage when investigating them.

Both caches use `chr-pos-ref-alt` keys without a source release or assembly.
Use a new cache after changing assembly, CADD version or gnomAD dataset.
The gnomAD dataset identifier is hardcoded in the fetcher; changing
`GNOMAD_API` alone changes only the endpoint.

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

`conservation_phylop` contains a CADD-derived proxy, not measured phyloP.
Independent conservation values change that training relationship. Apart
from `is_hbb`, the model has no gene identity feature: identical annotations
for any of the other four genes produce identical classifier inputs.

### Feature-build settings

| Setting | Default | Effect |
| --- | --- | --- |
| `FEATURE_BUILD_USE_REMOTE` | `1` | Enables real gnomAD/CADD lookups; `1`, `true`, `yes`, and `on` enable them |
| `FEATURE_BUILD_MAX_VARIANTS` | Unset | A positive integer limits the input rows sent to each fetcher; it is not random sampling. Rows left without features are dropped |
| `GNOMAD_API` | Public endpoint above | Overrides the query endpoint |
| `CADD_API_BASE` | `https://cadd.gs.washington.edu/api/v1.0/` | Overrides the base URL; retain its trailing slash |
| `CADD_VERSION` | `GRCh38-v1.7` | Selects the CADD build/version segment |

An offline synthetic check requires both the environment setting and flag:

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

Training compares a scaled logistic baseline and a Random Forest with
fold-local SMOTE; see [EVALUATION.md](EVALUATION.md) for split design and
recorded results. `--model all` saves the forest whenever it is included,
even if the console reports a different model with the highest AUC. The
saved forest does not require the training-only sampler at inference.

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

See [EVALUATION.md](EVALUATION.md) for the evidence supporting the reported
metrics and [USAGE.md](USAGE.md) for interpreting app output.

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

MalariaGEN [Pf7 contains *Plasmodium falciparum* parasite genomes](https://www.malariagen.net/resource/34/),
not human HBB variants. Its [access guide](https://malariagen.github.io/parasite-data/pf7/Data_access.html)
describes a separate resource; no Pf7 file or registration is required here.

Using UCSC conservation values would require feature-pipeline changes,
new provenance, retraining and evaluation. Optional ESM2 matrices are
generated separately; see [HEATMAPS.md](HEATMAPS.md). External data and
models retain their providers' terms and citation requirements.
