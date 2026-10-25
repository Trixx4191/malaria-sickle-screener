# Deploying the variant screener

## Live deployment — 24 October 2026

**URL:** https://malaria-sickle-screener.13-62-14-125.sslip.io

The app runs on `tidewatch-college-web-02` in `eu-north-1`, using its existing
reserved IP `13.62.14.125`. The free hostname resolves to that IP. Its separate
Nginx host redirects HTTP to HTTPS and proxies to `127.0.0.1:7860`.

The systemd service is `variant-screener.service`, enabled at boot. Release
`20261024T200915Z` is installed in
`/opt/variant-screener/releases/20261024T200915Z`; `/opt/variant-screener/current`
points to it. Each release has a fresh virtualenv; this deployment uses
Ubuntu 24.04's Python 3.12. The exact installed packages are recorded in
`deploy/requirements-runtime.lock` and in the deployed release.

Let's Encrypt HTTPS is active, with certificate expiry 22 January 2027.
`certbot.timer` renews it automatically, and a successful-renewal hook checks
and reloads Nginx. A renewal dry run including that hook passed. Port 443 was
enabled for HTTPS; the temporary SSH access rule was removed after deployment.
The two existing app services and their Nginx routes were preserved.

## Shared VM project URLs — 25 October 2026

| Project | Public HTTPS URL | Service / local port |
| --- | --- | --- |
| Tidewatch | [Open Tidewatch](https://tidewatch.13-62-14-125.sslip.io) | `tidewatch.service` / `3000` |
| F1 Strategy AI | [Open F1 Strategy](https://f1-strategy.13-62-14-125.sslip.io) | `f1-strategy.service` / `8100` |
| Variant Screener | [Open Variant Screener](https://malaria-sickle-screener.13-62-14-125.sslip.io) | `variant-screener.service` / `7860` |

The two additional names are configured in
`/etc/nginx/sites-available/project-names`, with a link under `sites-enabled`.
Their HTTP routes redirect to HTTPS while retaining the ACME challenge path.
Tidewatch preserves its default map query parameters; F1 preserves its API
paths, request limits, and proxy timeouts. The previous bare-IP and EC2-hostname
routes remain available.

Separate Let's Encrypt certificates named `tidewatch` and `f1-strategy` expire
on 23 January 2027 and renew through the existing `certbot.timer` and Nginx
reload hook. Application code and running service processes were not changed.

Browser verification found Tidewatch's page, map assets, and startup APIs all
working over its new HTTPS name. F1's dashboard, assets, session/demo endpoints,
and health endpoint work, but initial undercut/overcut chart requests return
500 because the demo loader accepts only the 2024 Bahrain race. Concurrent
rival-analysis startup requests can also return 429 under the existing F1
compute limit. These application/startup issues were recorded without changing
F1 source or weakening its request limits during the hostname setup.

## Gene reference UI: 25 October 2026

The current UI version is `gene-ui-21ae178287fc`. It uses a paper-and-ink
genetics reference layout, an actual GRCh38 locus strip, compact annotation
presets, and short labels. User-visible em dashes were removed, including
those in rendered API notes and structure descriptions. The gene metadata
uses Ensembl release 116; its sources and coordinate conventions are in
`docs/GENE_REFERENCE.md`.

Live assets are `style.gene-ui-21ae178287fc.css` and
`script.gene-ui-21ae178287fc.js`. The previous index and publication record
are saved under `/opt/variant-screener/ui-backups/gene-ui-21ae178287fc/`.
The model and backend process were preserved. All 12 UI regression checks
passed, including ACKR1 display with the existing DARC API key. Real-browser
checks verified all five locus records, clean copy, predictions, keyboard
focus, automatic canvas resizing, and the mobile layout.

## Earlier UI refresh: 25 October 2026

UI version `ui-953d46f2b39a` adds the compact annotation column, prominent
protein viewer, readable prediction summary, accessible controls, and a
responsive mobile layout. Model provenance, scientific color palettes, and
prediction behavior are preserved.

This update publishes only static files. The live index references
`style.ui-953d46f2b39a.css` and `script.ui-953d46f2b39a.js`; older assets remain
available for clients holding the previous HTML. The index was replaced
atomically after asset checksum verification. The backend process and model
were not restarted or replaced.

The previous index, new UI manifest, and publication record are in
`/opt/variant-screener/ui-backups/ui-953d46f2b39a/`. To roll back this UI only:

```sh
sudo cp /opt/variant-screener/ui-backups/ui-953d46f2b39a/index.html /opt/variant-screener/current/webapp/static/index.rollback.new
sudo mv /opt/variant-screener/current/webapp/static/index.rollback.new /opt/variant-screener/current/webapp/static/index.html
```

All 11 UI regression checks passed. Real-browser checks verified predictions,
manual residue controls, keyboard focus, responsive canvas sizing, color-key
popovers, and desktop/mobile layouts without JavaScript or network errors.

The serving app is FastAPI, static HTML/CSS/JS, and a six-feature scikit-learn
model. It does not need a GPU, Jupyter, raw ClinVar downloads, or request-time
ESM2 inference. Train models and generate optional heatmap JSON on a development
machine, then transfer those artifacts for serving.

## Existing AWS host assessment — 24 October 2026

AWS profile `sha` in `eu-north-1` contains the running Lightsail instance
`tidewatch-college-web-02`: 2 vCPUs, 2 GiB RAM, 60 GB disk. It is a Lightsail VM,
not an EC2 instance visible through `ec2 describe-instances`.

A query covering the previous seven days returned 41 hourly observations.
The mean of hourly average CPU utilization was 0.372%; the largest reported
CPU maximum was 50.389%. Latest burst capacity was 100%, and no returned
instance status-check observation reported failure. This is partial history,
not seven full days of continuous samples. CPU availability looks promising;
free memory and disk space still determine whether it can share this host.

An authorized read-only SSH check found 1,218 MiB available RAM, 53 GB free
disk (8% used), and load averages of 0.00. Existing applications are
`tidewatch.service` (Node, port 3000) and `f1-strategy.service` (Uvicorn,
loopback port 8100), with Nginx on port 80. Port 7860 was unused. Docker was
not present. The temporary SSH firewall addition was removed and the original
rules verified after the check.

**Recommendation: reuse this VM for a light-traffic deployment**, using a
separate service, loopback port 7860, and a dedicated Nginx virtual host.
Reassess if existing apps or prediction traffic increase substantially.

The inference model is approximately 2.45 MiB. Start with one Uvicorn worker
and one model job. More workers duplicate the scientific Python runtime and
model in memory. A 2 GiB host is a reasonable starting point for light traffic
if its existing services leave sufficient headroom; measure before deploying.

A local Python 3.11 / scikit-learn 1.9.0 measurement with the real model,
one CPU, one model thread, and 200 serial calls used approximately 181 MiB
RSS. Startup took 7.54 seconds; median prediction latency was 34.5 ms and
p95 was 59.7 ms. This is a local test, not a VM load test or a throughput
guarantee. Leave at least 512 MiB available for the worker and margin,
preferably about 1 GiB before adding the service.

The local development virtualenv has since been recreated and verified with
Python 3.14. Deployment creates a fresh environment on the host rather than
copying a local `venv/`.

## Prepare the artifacts

These files are intentionally ignored by Git and must be copied from a trusted
training run before building a production image:

```text
outputs/models/variant_screener_v1.pkl
outputs/models/model_meta.json
```

Optional substitution matrices go in `data/heatmaps/<GENE>.json`. The current
checkout has no generated matrices; the matrix panel stays hidden until those
files are supplied. The runtime never downloads or trains an ESM2 model.

The existing model was saved with scikit-learn 1.9.0. The runtime requirement
pins that version; update it together with a newly trained artifact. Scikit-learn
does not support loading persisted models across different library versions.
Only load trusted pickle/joblib files.

Production starts with `REQUIRE_REAL_MODEL=true`: missing, corrupt,
incompatible, or placeholder-trained artifacts cause startup to fail. A local
development session without this setting may use the explicitly labeled
synthetic demo when no model exists.

## Run locally without the research toolchain

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements-runtime.txt
REQUIRE_REAL_MODEL=true MODEL_N_JOBS=1 \
  uvicorn webapp.main:app --host 127.0.0.1 --port 7860 --workers 1
```

Use `requirements.txt` instead when working on training/data processing. Keep
the same scikit-learn pin when working with the existing model. The UI's 3D
viewer requires browser access to 3Dmol, RCSB, and AlphaFold. Prediction remains
available if those external services fail.

## Container deployment

The image installs only serving dependencies, runs as an unprivileged user,
checks `/api/health`, and limits model/native threads. The Docker build context
allows only app code, selected model artifacts, and optional heatmap JSON;
raw data, credentials, virtualenvs, and old frontend dependencies are excluded.

```sh
docker build -t variant-screener:local .
docker run -d --name variant-screener --restart unless-stopped \
  -p 127.0.0.1:7860:7860 \
  --log-opt max-size=10m --log-opt max-file=3 \
  variant-screener:local
curl --fail http://127.0.0.1:7860/api/health
curl --fail http://127.0.0.1:7860/api/model-info
```

Confirm `demo_mode` is false and `data_provenance` is `real`. Inspect startup
errors with `docker logs variant-screener`. A clean clone without the model
will build, but cannot start in production mode until artifacts are supplied.

For a shared host, put the app behind the existing reverse proxy on its own
hostname. Proxy to `127.0.0.1:7860`, forward `Host` and `X-Forwarded-*`, and
configure HTTPS for the chosen hostname. Keep the app port on loopback. Review
the host's existing services and proxy configuration before making changes.

To replace the container, build and verify a separately named candidate on a
different loopback port before switching the proxy. Keep the previous image
and artifacts available for rollback.

## Native service on the existing VM

The host already runs applications with systemd and Nginx, so deployment uses
the same approach. The applied service and HTTPS host configuration are in
`deploy/variant-screener.service` and `deploy/nginx.conf`. The HTTP-only
`deploy/nginx.conf.example` is available for bootstrapping a different hostname.

For another release, create `/opt/variant-screener/releases/<release>` with
the runtime source, trusted model artifacts, and optional heatmaps. Create its
`.venv` on the host and install `deploy/requirements-runtime.lock` to reproduce
the tested environment. Precreate `data/raw`, `data/processed`, `data/external`,
`outputs/figures`, and `outputs/models` so the dedicated `variant-screener`
account can start with read-only source/model files. Verify the candidate on
a separate loopback port before switching `current` and restarting the service.
Keep the previous release for rollback.

The systemd service starts one worker on loopback port 7860 and initially
limits it to 768 MiB RAM and one vCPU to protect the shared host. Confirm
startup and prediction success before enabling restart on boot or adding
the Nginx virtual host. For future configuration changes, validate Nginx with
`nginx -t` before reload. Keep the port-80 ACME challenge location reachable
so certificate renewals continue to work. The current Lightsail firewall
permits public HTTP and HTTPS and restricts SSH to the original approved IP.

Useful operations on the host:

```sh
sudo systemctl status variant-screener
sudo journalctl -u variant-screener -n 100 --no-pager
sudo systemctl restart variant-screener
sudo nginx -t
sudo systemctl status certbot.timer
sudo certbot renew --cert-name malaria-sickle-screener --dry-run --run-deploy-hooks --no-random-sleep-on-renew
```

The reload hook source is `deploy/renewal-reload-nginx.sh`. Certificate keys
and ACME account data remain under `/etc/letsencrypt` on the host and are
excluded from source archives.

## Capacity check

Run this read-only snapshot on the intended server:

```sh
sh scripts/check_vm_capacity.sh
# Or pass the script to an already authorized SSH connection:
ssh user@server 'sh -s' < scripts/check_vm_capacity.sh
```

Check available memory, filesystem space, current services, listening ports,
and container memory usage. Compare these with the measured app footprint
under representative traffic. Lightsail instance metrics cover CPU/burst/health;
host-level access is needed here to establish available RAM and filesystem
space. Do not infer free space from the plan's total disk size.

## Evaluation caveat

The historical CV applied SMOTE before the folds, and the old AFR subset
included training rows. Both were corrected and recomputed on 24 October 2026
using the existing real-feature matrix. The deployed artifact records
1,444 training and 361 held-out variants, test AUC 0.9825, and fold-local SMOTE
CV AUC 0.9700 ± 0.0052. Held-out predictions exactly match the earlier model.
The actual held-out AFR-frequency subset contains only 6 benign variants, so
its AUC is omitted. Historical AFR AUC = 1.000 remains withdrawn. The previous
local artifact is backed up under `outputs/models/backups/`.

## Verification performed

An isolated Python 3.11 environment with the matching scikit-learn version
passed all 17 Python tests and the real-model API/static-file smoke checks.
The 11 UI behavior checks pass with `node tests/test_ui.mjs`; they cover
external viewer failure, both heatmap schemas, AlphaFold URL discovery,
scientific colors, stale predictions, and residue-selection races.
Nginx and systemd configurations passed validation on the actual server.
The real VM service passed 136 valid prediction cases and rejected 19 invalid
requests; the same checks passed over public HTTPS. On-VM median/p95 latency
was 29.2/33.2 ms; this client's public HTTPS median/p95 was 562.7/942.8 ms,
including network and fresh HTTP connections. These are smoke-test observations,
not throughput guarantees.

An actual Chromium browser verified all five structures and four prediction
presets over HTTPS, including the real 3Dmol CDN, RCSB structures, and live
AlphaFold metadata/model downloads. It found no JavaScript errors, failed
external requests, or mobile overflow at 390 px. Service checks reported zero
restarts and no application exceptions. Docker is unavailable locally and was
not needed for this native deployment; its image remains unbuilt.

To run the Python checks after installing research dependencies plus `pytest`
and `httpx`, use `python -m pytest -q`. The temporary verification environment
does not replace the repository's existing `venv/`. To check a running release:

```sh
python3 scripts/smoke_deployment.py --base-url https://malaria-sickle-screener.13-62-14-125.sslip.io
```

References: [Lightsail metrics](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-resource-health-metrics.html),
[scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html).
