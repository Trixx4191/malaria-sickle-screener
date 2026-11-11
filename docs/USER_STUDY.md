# Platform use and evaluation scope

The West African Variant Screener has **500 users**. This count describes
people who used the application. It is separate from the genomic variants
used for model development and evaluation.

| Measure | Unit and count | Scope |
| --- | --- | --- |
| Platform use | 500 people | Application users |
| Model-development dataset | 1,805 ClinVar-labelled variants | 1,444 training and 361 held-out records |
| Model holdout | 361 variants | Denominator for classifier accuracy and AUC |
| Deployment smoke checks | 136 valid and 19 invalid requests per run | Automated engineering checks |

The saved model's 94.7% accuracy and 0.9825 AUC describe the variant holdout.
Using serving-compatible inputs gives 94.2% accuracy and AUC 0.9652 on the
same holdout. Neither pair measures outcomes for the 500 users.

## Evidence scope

The published material does not provide participant roles, recruitment,
site-level breakdowns, satisfaction scores or clinical outcomes. The user
count does not establish diagnostic accuracy or a representative cohort of
West African patients. Repeated sessions, scored variants and automated
requests have separate denominators.

Participant-level and identifiable records belong outside public version
control. The application does not implement feedback collection or case
export.

## Research paper

The [research paper](Alhassan_Salifu_Babamu_Variant_Screener_Paper.pdf)
reports computational evaluation and its limitations. See
[model evaluation](EVALUATION.md#lab-and-clinic-reports) for the relationship
between platform use and variant-level results, and [usage](USAGE.md) for
application controls and interpretation.
