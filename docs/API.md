# API reference

The FastAPI service accepts manually supplied annotations and returns a
classifier score. Paths are relative to the running app; examples use
`http://127.0.0.1:8000`. Docker uses port 7860 by default. Interactive schemas
are available at `/docs`, `/redoc` and `/openapi.json`.

The service has no authentication or endpoints for variant lookup, upload,
prediction history, report export or feedback. It does not explicitly persist
prediction bodies; deployment logging is controlled separately by operators.

The project's documented application evaluation involved **500 real users**.
Its [user-study record](USER_STUDY.md) is separate from API logging and model
evaluation metadata.

## Routes

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Process/model state |
| GET | `/api/model-info` | Loaded model metadata, provenance, features and accepted gene keys |
| POST | `/api/predict` | Score supplied annotations |
| GET | `/api/structure/{gene}` | Structure registry metadata; does not return a PDB file |
| GET | `/api/heatmap/{gene}` | Precomputed gene JSON, or 404 if unavailable/unknown |
| GET | `/` | Served HTML frontend; `/style.css` and `/script.js` are static assets |

## Health and model state

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/model-info
```

A strict real-data deployment returns this health object:

```json
{"status":"ok","demo_mode":false,"data_provenance":"real"}
```

Health returns HTTP 200 in synthetic and unverified modes too. It checks
neither prediction execution nor external services; inspect both flags.
`/api/model-info` returns:

| Field | Meaning |
| --- | --- |
| `demo_mode` | True only for the in-memory synthetic startup fallback |
| `data_provenance` | `real`, `synthetic_placeholder`, or `unknown` for bundles without provenance; other bundle values are returned unchanged |
| `meta` | Bundle evaluation metadata; for a non-demo bundle with no embedded metadata, falls back to local `model_meta.json` |
| `feature_order` | Ordered feature names actually used by this bundle |
| `genes` | `HBB`, `G6PD`, `DARC`, `HBA1`, `HBA2` |

A saved synthetic artifact can have `demo_mode: false`. Provenance comes
from the bundle, independently of the metadata sidecar.
`REQUIRE_REAL_MODEL=true` prevents startup without a compatible bundle marked
`real`. With strict mode off, only a missing artifact triggers the demo;
an invalid or scikit-learn-incompatible artifact causes startup failure.

## Predict

All five fields are required in a JSON body:

| Field | Type / accepted values | Meaning |
| --- | --- | --- |
| `gene_name` | String: `HBB`, `G6PD`, `DARC`, `HBA1`, `HBA2` | `DARC` is the API key for the interface's ACKR1 option; `ACKR1` is rejected |
| `gene_region` | String: `exonic`, `utr`, `intronic` | Encoded as 2, 1, 0 respectively |
| `allele_freq_afr` | Number, 0–1 inclusive | Frequency fraction, not percentage |
| `cadd_score` | Number, 0–60 inclusive | Supplied CADD Phred score |
| `conservation_phylop` | Number, −5–5 inclusive | Conservation feature; the recorded training data use a CADD-derived proxy |

Gene strings are stripped and uppercased; region strings are stripped and
lowercased. Missing fields, nulls, invalid labels and out-of-range/nonfinite
numbers return HTTP 422 with a FastAPI `detail` list. The browser's
conservation range is narrower (−3–3). Use actual numerical JSON values;
the request model is not configured for strict numeric typing. Unrecognized
extra fields are ignored by the current Pydantic model; they do not become
classifier inputs.

The server derives `is_hbb` from the gene and fixes `review_stars` to 1.
Residues, genomic coordinates, alleles and structure metadata are not submitted
or validated by this endpoint. It does not check that the input annotations
describe the same real variant. See [DATA.md](DATA.md) for feature definitions.

```bash
curl --fail-with-body http://127.0.0.1:8000/api/predict \
  -H 'Content-Type: application/json' \
  --data '{"gene_name":"HBB","gene_region":"exonic","allele_freq_afr":0.01,"cadd_score":25,"conservation_phylop":1}'
```

Scores depend on the loaded artifact. Response fields:

| Field | Type / meaning |
| --- | --- |
| `probability` | Number, 0–100; class-1 probability × 100 rounded to one decimal |
| `tier` | `benign` below 0.40, `uncertain` from 0.40 to below 0.75, `pathogenic` from 0.75, using the unrounded 0–1 score |
| `color` | `low`, `medium`, `high` for those three tiers |
| `notes` | Array of fixed-rule text notes triggered by frequency, CADD and the HBB flag |
| `contributions` | Ordered array of `{ "feature": string, "weight": number }` for this bundle's features |
| `contribution_method` | `heuristic` |
| `demo_mode`, `data_provenance` | Same model-state flags as above |

For a forest, contribution magnitudes come from global feature importances;
their signs use fixed feature midpoints. Models without `feature_importances_`
use equal magnitudes. Weights are normalized to the range −1 to 1 and are
not per-variant SHAP values.
A saved scaler, if present, is applied before `predict_proba`.

These tiers are application display thresholds, not clinical classifications.
The current service has no probability calibration step. Rounded percentages
can reach a boundary even when the unrounded score is on the other side.

## Structure metadata

```bash
curl --fail http://127.0.0.1:8000/api/structure/HBB
```

```json
{"pdb_id":"2HHB","chain":"B","source":"experimental","label":"Deoxyhemoglobin (T-state), chain B = beta-globin"}
```

The same five gene keys are accepted, normalized by trimming and uppercasing.
Unknown genes return HTTP 404. Records contain `pdb_id`, `chain`, `source`
(`experimental` or `alphafold`) and `label`. The browser downloads structure
files directly from RCSB or AlphaFold and downloads 3Dmol.js separately.
`DARC` maps to `AF-Q16570-F1`; the browser queries AlphaFold metadata for the
current PDB URL. See [GENE_REFERENCE.md](GENE_REFERENCE.md).

## Heatmap data

```bash
curl --fail http://127.0.0.1:8000/api/heatmap/HBB
```

Known gene keys are normalized by trimming and uppercasing. An unknown gene
returns 404 with `detail: "Unknown gene"`; a known gene without a JSON file
returns 404 with `detail: "Heatmap not precomputed for this gene yet"`.
The route reads `data/heatmaps/<GENE>.json` on each request and returns its
contents. It does not compute scores or validate the saved schema. Invalid
JSON is a server error. See [HEATMAPS.md](HEATMAPS.md) for the generated format.

## Verification

For a running real-data instance:

```bash
python scripts/smoke_deployment.py --base-url http://127.0.0.1:8000
```

The script checks provenance, all five genes, input normalization, valid
prediction ranges, invalid requests, static files, structure metadata and
optional heatmap availability. It sends 136 valid prediction requests and
19 invalid requests sequentially; it is not a clinical evaluation or a
concurrent load test. It uses the Python standard library and intentionally
fails for a demo or unverified-data model. External viewer downloads and
browser/WebGL behavior require a manual check.
