# Deployment history

This archive preserves screener deployment records from **24–25 October 2026**.
It also records the **30 October 2026** clarification acknowledging the
project's documented evaluation with **500 real users**.
It does not establish present availability, capacity, certificate status or
clinical performance. Use the [deployment guide](DEPLOYMENT.md) for current
commands and [Evaluation](EVALUATION.md) for the model results and limitations.

The original manifests and browser/smoke reports were retained locally under
the gitignored `outputs/deployment/` directory. They are not included in a
clean clone.

## 24 October 2026: native release

| Item | Recorded configuration |
| --- | --- |
| Public URL | <https://malaria-sickle-screener.13-62-14-125.sslip.io> |
| Host | Lightsail `tidewatch-college-web-02`, `eu-north-1` |
| Resources | 2 vCPUs, 2 GiB RAM, 60 GB disk |
| Reserved IP | `13.62.14.125` |
| Release | `20261024T200915Z` |
| Release directory | `/opt/variant-screener/releases/20261024T200915Z` |
| Active-release symlink | `/opt/variant-screener/current` |
| Runtime | Ubuntu 24.04, Python 3.12, scikit-learn 1.9.0 |
| Service | `variant-screener.service`, enabled at boot, loopback port 7860 |
| Proxy | Nginx, dedicated hostname, HTTP redirect to HTTPS |
| Model SHA-256 | `e599b0225e8b3f16cb4d64e2de9c53bfb0239cdc55b93003c425d40b9efccd5a` |

The release used a fresh virtualenv and the package versions preserved in
[requirements-runtime.lock](../deploy/requirements-runtime.lock). Nginx
and systemd configuration checks passed on the server. Let's Encrypt HTTPS
and a renewal dry run with the Nginx reload hook were verified. Existing
services and routes were preserved, and temporary SSH firewall access was
removed after deployment.

The predeployment host snapshot reported 1,218 MiB available RAM, 53 GB free
disk and load averages of 0.00. Forty-one hourly observations returned from
a seven-day CPU-metric query were partial history, not a continuous seven-day
record. These observations supported deployment at that time; they are not
current capacity estimates.

### Software verification and serial timings

The archived release checks reported 17 Python tests passing, 136 valid
prediction requests succeeding, and 19 invalid requests being rejected.
The prediction checks passed on the VM and through public HTTPS.

| Measurement | Setup | Median / p95 |
| --- | --- | --- |
| Local prediction calls | Python 3.11, one CPU/model thread, 200 serial calls | 34.5 / 59.7 ms |
| VM smoke requests | Native service, serial HTTP requests | 29.2 / 33.2 ms |
| Public HTTPS smoke requests | Client network and fresh HTTP connections included | 562.7 / 942.8 ms |

The local process used approximately 181 MiB RSS and took 7.54 seconds to
start; the saved model was approximately 2.45 MiB. These are measurements of
one setup, not load-test results or throughput guarantees.

A Chromium check covered all five structures, four illustrative
presets, 3Dmol/RCSB/AlphaFold downloads, and a 390 px mobile layout. The report
recorded no JavaScript errors, failed external requests or mobile overflow.
Service checks reported no restarts or application exceptions during those
checks. Docker was unavailable locally; no container build was verified in
this native deployment.

The local evidence directory is `outputs/deployment/20261024T200915Z/`,
including `release-manifest.json`, `model-validation.json`,
`browser-report.json` and `public-smoke.json`.

### Corrected model evaluation

The artifact recorded 1,444 training and 361 held-out variants from 1,805
real-feature rows, held-out AUC 0.9825, and five-fold training CV AUC
0.9700 ± 0.0052 with SMOTE fitted inside each fold. The correction preserved
the previous model's held-out predictions.

The earlier CV resampled before fold splitting, and the earlier
AFR-frequency evaluation included training rows. Those results were
superseded; the reported AFR AUC of 1.000 was withdrawn. The corrected
held-out AFR-frequency subset contained only six variants, all benign,
so no AUC could be calculated. This is retrospective computational
evaluation, not validation in a West African clinic cohort.

## 25 October 2026: static interface publications

Two static-only updates were recorded: `ui-953d46f2b39a`, followed by
`gene-ui-21ae178287fc`. The latter added the Ensembl 116 / GRCh38 gene
reference strip and preserved ACKR1 display with the API key `DARC`.
The backend process and model were not restarted or replaced.

Assets were uploaded with versioned names, checked by checksum, then
referenced by an atomically replaced index. Older assets and the previous
index were retained for cached clients and rollback. The last publication
used `style.gene-ui-21ae178287fc.css` and
`script.gene-ui-21ae178287fc.js`.

Archived regression and real-browser checks covered the five gene records,
predictions, residue controls, keyboard focus, canvas resizing and
desktop/mobile layouts. The latest saved index and publication record were
placed under `/opt/variant-screener/ui-backups/gene-ui-21ae178287fc/`.
The corresponding local evidence directory is
`outputs/deployment/gene-ui-21ae178287fc/`; it includes the UI manifest,
publication record, gene-reference verification and browser reports.

## 30 October 2026: documented user evaluation acknowledged

The project owner confirmed that the report is based on documented use of
the application by **500 real users**. See the [user-study record](USER_STUDY.md)
for the report reference and evidence scope. This date records the clarification;
it does not establish when the user evaluation took place.

The 500 users are a human participation count. The automated prediction,
browser and deployment checks above are separate engineering records, and the
1,805 variants in the model evaluation are separate variant records. Neither
the participation count nor the deployment checks supply clinical diagnostic
accuracy or establish a patient validation cohort.
