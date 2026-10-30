# Using the screener

This guide covers the FastAPI interface reviewed on 30 October 2026. Start
with the [README](../README.md#run-locally) for installation and model loading.
Research results and their scope are documented in [EVALUATION.md](EVALUATION.md).

The project's documented application evaluation involved **500 real users**,
as confirmed by the project owner on 30 October 2026. The
[user-study record](USER_STUDY.md) acknowledges that participation and the
associated report. This user count is separate from the 1,805 variants used
for model development and evaluation.

## Before scoring

Prepare annotations for the same variant and genome build; the research
pipeline uses GRCh38. The application scores the supplied values without
retrieving or verifying a variant record. Residue selection is a separate
viewer control. VCF upload and case history are not supported.

Read the status in the top right:

| Status | Meaning |
| --- | --- |
| `real data · Random Forest` (or Logistic Regression) | A saved bundle reports real feature provenance |
| `Demo mode · synthetic data` | A temporary model was fitted to synthetic examples because no artifact was supplied |
| `Warning · unverified training data` | A loaded artifact has placeholder or unknown feature provenance |
| `Model unavailable` | The browser could not retrieve model information; check connectivity and reload |

Only a real-data model displays a test AUC. The training count excludes the
held-out test rows for the current artifact. Hover over the status/count for
more detail, or inspect `/api/model-info` using the [API guide](API.md).

## Score annotations

1. Select **Gene**. The interface displays ACKR1; requests use the legacy key
   `DARC`. The locus strip shows a reference gene span, not the scored variant.
2. Select **Gene region**: Exonic, UTR or Intronic / other.
3. Set **AFR allele frequency**, **CADD Phred score** and **Conservation**.
   Frequency is a fraction: `0.01` means 1%. Conservation is a CADD-derived
   proxy in training: `clip(CADD / 40, -3, 3)`. Independently measured phyloP
   changes that feature definition; see [DATA.md](DATA.md).
4. Select **Score variant** and read the **Model score** panel. Changing any
   model input clears the old score and displays “Inputs changed. Score again.”

The browser sliders cover frequency 0–1 in steps of 0.001, CADD 0–60 in steps
of 0.5, and conservation −3–3 in steps of 0.1. For finer numerical inputs use
the [API](API.md), which accepts conservation −5–5. Keep original annotations
when recording a case; displayed slider precision may be insufficient for a
rare allele.

Selecting a **Preset** fills the controls and immediately submits a score.
These four examples are illustrative feature combinations. They are not
retrieved annotations or validated examples of named variants.

## Read the output

**Pathogenicity estimate** is the model's class-1 output multiplied by 100 and
rounded to one decimal place. The interface assigns these fixed tiers using
the unrounded model score:

| Model score | Displayed tier |
| --- | --- |
| Below 40% | LIKELY BENIGN |
| 40% to below 75% | UNCERTAIN / BORDERLINE |
| 75% and above | LIKELY PATHOGENIC |

A displayed percentage may round to a tier boundary. No probability
calibration step is implemented, and the tiers are application categories
rather than clinical classifications. Notes follow fixed rules about
frequency, CADD and the HBB flag. Expand **Feature weights** for normalized
heuristic weights, separate
from per-variant SHAP explanations.

The serving model distinguishes gene identity only through an HBB flag.
With otherwise identical inputs, G6PD, DARC, HBA1 and HBA2 produce the same
score. `review_stars` is fixed to 1. See [evaluation limitations](EVALUATION.md#limitations)
for training coverage and the scope of the recorded results.

## Explore the protein

The **Protein structure** panel loads external reference structures. Drag to
rotate and scroll to zoom. Enter a positive whole-number **Residue**, then
leave the field to highlight it; **Focus** returns the camera to that residue.
**Reset** restores the overall view and retains the selection. **PDB file**
downloads the loaded reference structure, not a patient-specific mutant model.

Helices are red, sheets yellow and loops green; other chains are faded.
Residue atom colors are separate from model-score colors. Viewer residue
numbers refer to the selected structure's chain. Heatmap sequence positions,
PDB residue numbering and transcript variant notation may differ; the app
does not map between them. Preset highlighting illustrates a residue without
changing the structure's amino-acid identity or the classifier input.

The [gene reference guide](GENE_REFERENCE.md) lists the structure records. The
ACKR1/DARC viewer uses a predicted AlphaFold model. Missing viewer downloads or
unsupported WebGL can leave the structure unavailable while scoring continues.

## Optional substitution map

**Amino acid substitutions** appears only if a precomputed map can be loaded
for the selected gene. Select a position to list its amino-acid substitutions
ordered by ESM2 score. These are sequence-model scores, separate from the
Random Forest percentage and tier. They do not feed into prediction and
selecting a heatmap position does not select a viewer residue.
See [HEATMAPS.md](HEATMAPS.md) for generation and interpretation.

## Common problems

| Symptom | Action |
| --- | --- |
| Prediction unavailable or timed out | Check the app connection, retry, and record the time and message if it persists; browser prediction requests time out after 20 seconds |
| Model unavailable | Reload; an operator should check `/api/health`, `/api/model-info` and service logs |
| Unexpected synthetic status | An operator should check the artifact path and strict model setting, then restart; see [deployment](DEPLOYMENT.md) |
| Structure unavailable | Check access to 3dmol.org, RCSB and AlphaFold; reselect the gene after connectivity returns |
| Residue not present | Check chain numbering and the selected structure; unavailable residues cannot be highlighted |
| No substitution panel | A missing or failed map remains hidden; scoring does not require a map |
| Old interface after an update | Hard-refresh the browser; have the operator confirm the deployed source revision |

## Record lab and clinic feedback

The [500-user study record](USER_STUDY.md) acknowledges the documented user
evaluation. Use the fields below when preparing follow-up documentation or
recording lab or clinic use; the participation count alone does not specify
the users' roles or study settings. Keep usability and workflow observations
separate from comparisons against independent variant classifications. The
[evaluation record](EVALUATION.md#lab-and-clinic-reports) describes how these
forms of evidence relate to the model evaluation.

| Field | What to record |
| --- | --- |
| Session context | Date/time and timezone, anonymous site label, browser/device, network conditions and user role |
| Purpose and source | Task performed, type of evaluation, and the dated source document supporting the report |
| Version | Deployed source revision if available, app URL, `/api/model-info` response and model artifact identifier/hash supplied by the operator |
| Inputs and action | Exact five annotation values, their sources/build, whether a preset was used, and the steps taken |
| Output | Returned percentage/tier and provenance, or exact error text; screenshots can be redacted |
| Independent comparison, if available | Reference classification, source/method/date, and independence from the app; include disagreements and uncertain cases |
| Usability | What the user expected, what happened, delays, confusing controls and whether they completed the task |
| Counts | Sessions/variants attempted, succeeded and failed, plus how cases were selected; specify repeat attempts |

Share de-identified observations and keep identifiable source records outside
public version control. Use separate study records for documentation;
in-app feedback collection and case export are not implemented.
Obtain the source revision and artifact hash from the operator; the API does
not include them, and an AUC value does not identify a model version.
