# Using the screener

Reviewed against the current interface on 30 October 2026. This guide describes
the research prototype served by `webapp/main.py`. For installation and model
loading, start with the [README](../README.md#run-locally).

## Before scoring

The application accepts manually supplied annotations. It does not accept a
VCF, identify a variant from a residue, retrieve annotations for a patient, or
store a case history. Use annotations for the same variant and genome build;
the current research pipeline uses GRCh38. The API cannot check their source
or that the numerical values describe a particular variant.

Read the status in the top right:

| Status | Meaning |
| --- | --- |
| `real data · Random Forest` (or Logistic Regression) | A saved bundle reports real feature provenance; this does not imply clinical validation |
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
   proxy in the recorded training data; measured phyloP is not interchangeable
   without evaluating a changed feature definition. The proxy formula is
   documented in [DATA.md](DATA.md).
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

A displayed percentage may round to a tier boundary; the tier is based on the
unrounded value. These labels are application categories. The implementation
does not calibrate the percentage or apply clinical classification guidelines.
Notes are fixed rules about frequency, CADD and the HBB flag. They are not an
independent expert assessment. Expand **Feature weights** for normalized,
heuristic relative weights; these are not SHAP values or causal explanations.

The serving model distinguishes gene identity only through an HBB flag.
With otherwise identical inputs, G6PD, DARC, HBA1 and HBA2 produce the same
score. `review_stars` is fixed to 1. The recorded matrix has no DARC training
rows. AFR refers to the queried gnomAD population group, not a clinic-specific
or independently validated West African cohort. See the full
[data and evaluation limitations](DATA.md).

The footer states **Research use only** and **Not validated for clinical
use**. Clinic use or user feedback alone does not change that status.

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

## Record feedback from use in clinics

No clinic findings are recorded in this documentation update. For the next
review, share de-identified observations using the following fields. Keep
usability observations separate from comparisons against independently
established variant classifications.

| Field | What to record |
| --- | --- |
| Session context | Date/time and timezone, anonymous site label, browser/device, network conditions and user role |
| Version | Deployed source revision if available, app URL, `/api/model-info` response and model artifact identifier/hash supplied by the operator |
| Inputs and action | Exact five annotation values, their sources/build, whether a preset was used, and the steps taken |
| Output | Returned percentage/tier and provenance, or exact error text; screenshots can be redacted |
| Independent comparison, if available | Reference classification, its source/date and whether it was independent of the app; include disagreements and uncertain cases |
| Usability | What the user expected, what happened, delays, confusing controls and whether they completed the task |
| Counts | Sessions/variants attempted, succeeded and failed, plus how cases were selected; specify repeat attempts |

Do not include patient names, contact information, chart numbers or other
identifying details in shared feedback. The app has no feedback submission,
case export or clinical-outcome collection feature; observations must be
recorded separately. Current API responses do not include the source revision
or an artifact hash, so obtain those from the operator rather than infer them
from an AUC value.
