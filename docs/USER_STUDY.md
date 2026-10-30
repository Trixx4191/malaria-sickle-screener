# Documented 500-user application evaluation

Updated **30 October 2026**.

The Malaria–Sickle Cell Screener project has a **documented application-use
evaluation involving 500 real users**. The project owner confirmed that the
supplied report comes from this documented use on **30 October 2026**. This
record incorporates that clarification into the project documentation.

## Report and source

The associated report is
[`Revised_Malaria_Sickle_Cell_Screener_Report.docx`](reports/Revised_Malaria_Sickle_Cell_Screener_Report.docx).
The project copy acknowledges the documented 500-user evaluation and the
project owner's clarification. The originally supplied document is retained
outside this repository.

The original source document has SHA-256
`382d11eba9fa2beed164c489e4056e3bf02d61915b6ba62048753288198578db`.

Earlier wording in the report and project documentation treated human-use
evidence as unavailable. The project owner's clarification supersedes that
wording about the existence of documented user participation. The underlying
variant-level model results retain their own evaluation scope.

| Item | Recorded information |
| --- | --- |
| Application users | 500 real users |
| Activity | Documented use of the application, associated with the supplied report |
| Participant-count source | Project-owner clarification received on 30 October 2026 |
| Associated report | `Revised_Malaria_Sickle_Cell_Screener_Report.docx` |
| Study dates | Not specified in the material available for this documentation update; 30 October is the clarification date |
| Roles, sites and recruitment | Not specified in the material available for this documentation update |
| Quantitative user outcomes | No satisfaction, completion-rate or other user-outcome values are supplied in this update |

## Evaluation denominators

| Evaluation | Unit and count | Interpretation |
| --- | --- | --- |
| Documented application-use evaluation | 500 real users | Human participation in documented application use |
| Retained model-development dataset | 1,805 ClinVar-labelled variants | Variant-level data, split into 1,444 training and 361 holdout records |
| Historical model holdout | 361 variants | Denominator for the recorded model accuracy and AUC |
| Deployment smoke checks | 136 valid and 19 invalid prediction requests per run | Automated engineering checks |

The 500-user count is a participant count. Repeated sessions, predictions and
automated requests have separate denominators. The reported 94.7% accuracy
and 0.9825 AUC come from the historical variant holdout; they are not measured
user-outcome statistics. Documented application use does not by itself
establish clinical diagnostic performance.

## Maintaining the study record

Further study summaries should cite the relevant report section or source
record and include study dates, participant roles and settings, recruitment,
software/model version, tasks and measurement methods. Report attempted,
completed, failed and repeated tasks with explicit denominators when these
counts are available. Record satisfaction, usability and independent clinical
comparison findings only with their supporting measurements.

Participant-level records and identifiable information are not included in
this repository update. Study summaries can reference de-identified evidence
retained by the project team without publishing individual records.

See [Evaluation](EVALUATION.md#lab-and-clinic-reports) for the relationship to
model results, [Usage](USAGE.md#record-lab-and-clinic-feedback) for
documentation fields, and [Deployment history](DEPLOYMENT_HISTORY.md) for
dated operational checks.
