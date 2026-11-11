# Model evaluation

The saved Random Forest is evaluated against a retained ClinVar feature
matrix. Platform use and variant-level prediction have separate units;
see [platform use and evaluation scope](USER_STUDY.md).

## Results

| Measure | Result | Scope |
| --- | --- | --- |
| Saved-model AUC-ROC | 0.9825 | 361 held-out variants, training-time inputs |
| Saved-model binary accuracy | 94.7% | Binary predictions on the same holdout |
| Serving-compatible AUC-ROC | 0.96515 | Review quality fixed to 1 |
| Serving-compatible binary accuracy | 94.18% | Review quality fixed to 1 |
| Training CV AUC | 0.9700 ± 0.0052 | Five stratified folds; ± is fold standard deviation |
| AFR-frequency subset AUC | Undefined | Six held-out variants above 0.01 AFR frequency, all benign |

The split uses seed 42, with 1,444 training and 361 held-out variants. The
forest has 200 trees and maximum depth 10. Each CV fold fits SMOTE only on
its training rows. The final forest fits the oversampled training split;
test rows remain excluded from fitting. AFR-frequency analyses use only
the held-out rows.

Binary accuracy uses the classifier's `predict` output. The interface
applies three score bands at 40% and 75%; the reported binary metric does
not measure tier accuracy. Fold standard deviation is not a confidence
interval.

## Dataset coverage

Feature construction retained 1,805 of 2,177 parsed ClinVar records. The
retained matrix contains 1,805 distinct variant IDs and genomic keys.

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

Feature construction retained 95.0% of benign records and 66.2% of
pathogenic records. Performance on this subset does not establish
performance on variants without resolvable features.

The matrix has 1,776 exonic-coded rows, 29 intronic/other-coded rows and no
UTR-coded rows. These categories are inferred from variant-name text, not
transcript annotation. Of the AFR frequencies, 1,561 are zero and 244 are
positive. The gnomAD client can encode missing source coverage as zero;
these counts do not establish observed absence.

## Limitations

- **Population scope:** gnomAD genome AFR frequency is an annotation. The
  holdout is not an independent West African patient cohort. Its
  high-frequency subset contains only six benign variants, so AUC is
  undefined for that subset.
- **Feature dependence:** `conservation_phylop` equals
  `clip(cadd_score / 40, -3, 3)` in every retained row. It is a CADD-derived
  proxy, not an independent phyloP measurement. The
  [paper](Alhassan_Salifu_Babamu_Variant_Screener_Paper.pdf) includes feature
  ablations; the headline classifier score alone does not establish the
  added value of African allele frequencies.
- **Review quality at serving:** training-time evaluation uses
  ClinVar-derived `review_stars`; the app fixes it to 1. This input change
  alters six binary predictions and 21 display tiers. Review status comes
  from the same source as the labels, so performance cannot be attributed
  solely to molecular annotations.
- **Gene and input coverage:** only the HBB flag encodes gene identity.
  Otherwise identical inputs give the same score for G6PD, HBA1, HBA2 and
  DARC. DARC has no training rows. Accepted API ranges extend beyond the
  observed training coverage; input validation does not establish accuracy.
- **Split and uncertainty:** the headline split is stratified at row level,
  without holding related variants, loci or feature-vector groups together.
  The paper reports separate grouped and gene-held-out comparisons. These
  internal analyses do not establish patient-level generalisation or
  probability calibration.
- **Interpretation:** score thresholds and notes are application rules.
  Feature bars are heuristic weights. Protein structures and optional ESM2
  maps are separate reference tools and do not validate a prediction.

See [data construction](DATA.md) for filtering, caches and missing-data
handling. The limitations describe the scope of the evidence; they do not
quantify an error rate outside the evaluated dataset.

## Artifacts and reproducibility

| Local file | Purpose |
| --- | --- |
| `data/processed/clinvar_clean.csv` | Parsed labels and source coordinates |
| `data/processed/features.csv` | Retained feature matrix |
| `data/processed/features_provenance.json` | Feature provenance and retained/dropped counts |
| `outputs/models/variant_screener_v1.pkl` | Saved classifier bundle |
| `outputs/models/model_meta.json` | Split counts, AUC, CV method and AFR subset |

The matching local files have these SHA-256 values:

```text
data/processed/features.csv
d056b0879c9fcbd720ccf5bfc447c505bfc87d1f4a2ee5f96c3e410dd15494d3

outputs/models/variant_screener_v1.pkl
e599b0225e8b3f16cb4d64e2de9c53bfb0239cdc55b93003c425d40b9efccd5a

outputs/models/model_meta.json
135f890f0587ec845a5b101bc6ce066dbfdfbff8459a293b54b4049c87d2b8c3
```

Data and models are gitignored. A clean clone uses the labelled synthetic
demo unless a trusted, compatible model bundle is supplied. Reproducing
these results requires the matching feature matrix and saved model; a new
download from mutable data services can produce a different matrix.
Checksums identify the retained files but do not supply missing upstream
source snapshots. Source-release identifiers and raw-source hashes are not
fully recorded by the feature sidecar. Per-row predictions are not bundled
in a clean clone.

Offline SHAP plotting and ESM2 precomputation are implemented separately.
Their implementation does not establish that a particular figure or map
accompanies a model bundle.

## Lab and clinic reports

The 500-user count describes application use. It is separate from the 1,805
variant records and 361-variant holdout. Public material does not provide
participant roles, recruitment, site-level outcomes or independent clinical
comparisons. Application use alone does not establish clinical performance.

See [platform use](USER_STUDY.md), [usage](USAGE.md) and the
[research paper](Alhassan_Salifu_Babamu_Variant_Screener_Paper.pdf) for the
software's scope, controls and computational results.
