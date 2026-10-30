# Evaluation record

Repository and local artifacts reviewed on **30 October 2026**. Metrics below
come from the recorded **24 October 2026** evaluation. The review checked
artifact hashes, metadata and dataset counts; it did not retrain the model
or recompute its held-out predictions.

## Recorded results

| Measure | Result | Scope |
| --- | --- | --- |
| Held-out AUC-ROC | 0.9825 | 361 test variants |
| Binary accuracy | 94.7% | Standard binary classifier predictions on those test variants |
| Training CV AUC | 0.9700 ± 0.0052 | Five stratified folds; ± is fold standard deviation |
| AFR-frequency subset AUC | Undefined | 6 held-out variants above 0.01 AFR frequency, all benign |

The split uses seed 42, with 1,444 training and 361 held-out variants. The
Random Forest has 200 trees and maximum depth 10. Each CV fold fits SMOTE
only on its training rows. The final forest fits the oversampled training
split; the test rows remain excluded from fitting.

The binary accuracy uses the classifier's `predict` output. The interface
instead applies three score bands at 40% and 75%; its tier accuracy has not
been measured by the reported binary metric. The fold standard deviation
is not a confidence interval.

## Dataset coverage

Feature construction retained 1,805 of 2,177 parsed ClinVar records. The local
snapshot contains 1,805 distinct variant IDs and genomic variant keys.

| Gene | Retained variants |
| --- | ---: |
| HBB | 1,050 |
| G6PD | 523 |
| HBA2 | 130 |
| HBA1 | 102 |
| ACKR1 / DARC | 0 |

| Label | Parsed records | Retained records | Excluded records |
| --- | ---: | ---: | ---: |
| Benign / likely benign | 1,262 | 1,199 | 63 |
| Pathogenic / likely pathogenic | 915 | 606 | 309 |
| Total | 2,177 | 1,805 | 372 |

Exclusion during feature construction affects the label groups differently:
95.0% of benign records and 66.2% of pathogenic records were retained. The
evaluation therefore describes the retained subset; it does not establish
performance on variants without resolvable features.

The retained matrix has 1,776 exonic-coded rows, 29 intronic/other-coded rows
and no UTR-coded rows. These categories are inferred from variant-name text,
not transcript annotation. Of the AFR frequencies, 1,561 are zero and 244
are positive. Missing source coverage can also be encoded as zero by the
current gnomAD client; these counts do not establish observed absence.

## Limitations

- **Population scope:** gnomAD genome AFR frequency is an annotation, not a
  cohort of West African patients. No independent clinical, geographic,
  temporal or gene-held-out evaluation is recorded. The held-out
  high-frequency subset has only six benign variants.
- **Feature dependence:** `conservation_phylop` equals
  `clip(cadd_score / 40, -3, 3)` in every retained row. It is a CADD-derived
  proxy, not an independent phyloP measurement. No CADD-only or frequency
  ablation is recorded, so the added value of AFR frequency is unmeasured.
- **Review quality at serving:** training and evaluation use ClinVar-derived
  `review_stars` values; the app fixes this input to 1. No reevaluation with
  that serving value fixed is recorded. Review status
  comes from the same source as the labels; its contribution requires a
  separate ablation before attributing performance to molecular annotations.
- **Gene and input coverage:** only the HBB flag encodes gene identity.
  Otherwise identical inputs produce the same score for G6PD, HBA1, HBA2
  and DARC. DARC has no training rows. The API accepts regions and numerical
  ranges beyond observed training coverage; validation of an input range
  does not establish model performance throughout that range.
- **Split and uncertainty:** the split is stratified by label at the row
  level. Related variants, loci and feature-vector groups are not held out
  as groups. No patient-level generalization, confidence intervals or
  probability calibration is reported.
- **Interpretation:** score thresholds and notes are application rules.
  The feature bars are heuristic weights. Protein structures and optional
  ESM2 maps are separate reference tools; they do not validate a prediction.

See [DATA.md](DATA.md) for source filtering, cache formats and missing-data
handling. These limitations constrain the conclusions that can be drawn from
the reported metrics; they are not measurements of the size of an error.

## Evaluation corrections

The 24 October run corrected two earlier evaluation procedures:

| Earlier procedure | Corrected procedure |
| --- | --- |
| SMOTE applied before CV fold splitting | SMOTE fitted separately within each training fold |
| AFR-frequency evaluation included training rows | AFR-frequency evaluation restricted to held-out test rows |

The earlier AFR-subset AUC of 1.000 is withdrawn. The historical validation
record reports identical held-out probabilities and binary predictions
between the previous and corrected saved forests; the corrected records
establish the split counts and fold-local CV method.

## Evidence and reproducibility

The local evidence files are:

| File | Evidence |
| --- | --- |
| `data/processed/clinvar_clean.csv` | Parsed labels and source coordinates |
| `data/processed/features.csv` | Retained feature matrix |
| `data/processed/features_provenance.json` | Real-feature marker, retained and dropped counts |
| `outputs/models/model_meta.json` | Split counts, AUC, CV method and AFR subset |
| `outputs/deployment/20261024T200915Z/model-validation.json` | Recorded held-out accuracy/AUC, artifact comparison and hashes |
| `outputs/deployment/20261024T200915Z/release-manifest.json` | Hashes of the published model and metadata |

The following SHA-256 values match the local files and the recorded release
evidence as of 30 October:

```text
data/processed/features.csv
d056b0879c9fcbd720ccf5bfc447c505bfc87d1f4a2ee5f96c3e410dd15494d3

outputs/models/variant_screener_v1.pkl
e599b0225e8b3f16cb4d64e2de9c53bfb0239cdc55b93003c425d40b9efccd5a

outputs/models/model_meta.json
135f890f0587ec845a5b101bc6ce066dbfdfbff8459a293b54b4049c87d2b8c3
```

These data, artifacts and deployment reports are gitignored; they are not
available from a clean clone. A reviewer needs the matching artifact package
to rerun the recorded evaluation. The feature sidecar does not encode source
release dates or raw-source hashes, and held-out row IDs/predictions are not
saved separately. New downloads from mutable ClinVar/CADD/gnomAD sources can
produce a different matrix. The hashes identify this snapshot; they do not
supply the missing source snapshots.

ROC and confusion-matrix images are present locally. Offline SHAP generation
and optional ESM2 precomputation are implemented, but no SHAP figures or
heatmap JSON files are present in the reviewed artifact set.

## Lab and clinic reports

No lab or clinic outcome measurements are included in the current evidence
set. Reports supplied after this review should identify the source document,
dates, software/model version, task, sample-selection method and denominators.
Separate usability and workflow observations from comparisons against an
independent variant classification.

Report completed, failed, repeated and excluded attempts alongside any
agreement measurements. Describe the reference method and uncertainty before
making an accuracy or clinical-validation claim. Use de-identified summaries;
retain source documents outside public version control. The
[usage guide](USAGE.md#record-lab-and-clinic-feedback) lists the fields to record.
