# Deployment

Reviewed against the repository on **30 October 2026**. The app serves a
FastAPI backend and plain HTML/CSS/JavaScript, with no frontend build step.
Serving needs the model and runtime dependencies; training data, a GPU,
Jupyter and ESM2 inference are not required.

This guide covers installation, updates and operational checks.
[Deployment history](DEPLOYMENT_HISTORY.md) records the 24–25 October server
checks. For inputs and model interpretation, see [Usage](USAGE.md) and [API](API.md).

The project also has a documented application evaluation involving **500 real
users**, recorded in the [user-study record](USER_STUDY.md). That evaluation
is separate from the automated operational checks described here.

On **30 October 2026**, read-only HTTPS checks of the public page,
`/api/health` and `/api/model-info` returned HTTP 200. Health reported
`demo_mode: false` and `data_provenance: "real"`; model metadata matched the
recorded 1,444/361 split and AUC 0.9825. This check covered page delivery and
model state, not prediction requests, external structures, browser behavior,
host capacity or certificate renewal.

## Artifacts and dependencies

Run commands from the repository root. Copy this pair from a trusted training
run before starting a production service or building its image:

```text
outputs/models/variant_screener_v1.pkl
outputs/models/model_meta.json
```

Both files are gitignored. The bundle supplies the estimator, feature order,
provenance and normally evaluation metadata. The JSON sidecar supplies
metadata only when the bundle has none embedded; editing it does not replace
the model or change provenance. Only load trusted pickle/joblib artifacts.

The runtime pins scikit-learn **1.9.0** to match the recorded artifact. The
loader rejects incompatible versions and invalid bundles. Update dependencies
alongside a replacement artifact, then verify it before release. Models load
once per process. Restart workers after replacement; rebuild and recreate
containers that package the artifact.

Optional heatmaps belong in `data/heatmaps/<GENE>.json`, using `DARC.json` for
ACKR1. Missing maps return 404 and leave the panel hidden. Generate them
separately using the [heatmap guide](HEATMAPS.md).

## Run locally

The container uses Python 3.11; the recorded native deployment uses Python
3.12. Create a fresh environment with a compatible interpreter:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-runtime.txt
REQUIRE_REAL_MODEL=true MODEL_N_JOBS=1 \
  python -m uvicorn webapp.main:app --host 127.0.0.1 --port 7860 --workers 1
```

Open <http://127.0.0.1:7860>. The [README](../README.md#run-locally) uses port
8000 for development; use the corresponding port in verification commands.
Install `requirements.txt` instead for training and data work.

The optional structure viewer requires WebGL and browser access to
`3dmol.org`, `files.rcsb.org` and `alphafold.ebi.ac.uk`. Predictions continue
when these downloads fail.

### Model states and environment

| Variable | Default / configured value | Behavior |
| --- | --- | --- |
| `REQUIRE_REAL_MODEL` | Unset locally; `true` in Docker/systemd | Values `1`, `true`, `yes` or `on` require a loaded bundle with `real` provenance. |
| `MODEL_N_JOBS` | `1` | Positive integer applied to models with an `n_jobs` setting. |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` | `1` in Docker/systemd | Limit native-library threads. |

With strict mode off, a missing pickle triggers the labeled synthetic demo.
An existing corrupt or incompatible pickle still fails to load. Loaded
placeholder or legacy bundles retain their provenance warnings; strict mode
rejects them.

Check both flags in the health response:

```json
{"status":"ok","demo_mode":false,"data_provenance":"real"}
```

HTTP 200 alone is insufficient: demo mode also reports `status: "ok"`.
`real` identifies feature provenance, not clinical validation. The app remains
a research prototype. `/api/model-info` reports the loaded evaluation metadata,
feature order and accepted gene keys; ACKR1 uses `DARC` in API requests.

## Docker

The root Dockerfile installs runtime dependencies, runs as UID/GID 10001,
and starts one worker on port 7860 with a concurrency limit of 16. Its
health check requests `/api/health`; startup enforces real provenance.
The build-context allowlist includes serving code, selected model artifacts
and optional heatmap JSON, excluding raw data, credentials and virtualenvs.

```sh
docker build -t variant-screener:local .
docker run -d --name variant-screener --restart unless-stopped \
  -p 127.0.0.1:7860:7860 \
  --log-opt max-size=10m --log-opt max-file=3 \
  variant-screener:local
docker logs variant-screener
python3 scripts/smoke_deployment.py --base-url http://127.0.0.1:7860
```

An image can build without the artifact but will fail at startup. Copy
artifacts before building. For an update, build a separately tagged image
and run a candidate on another loopback port. Verify it before switching the
proxy, and retain the old image and artifacts for rollback.

For a Hugging Face Space, use the Docker SDK, provide the source and trusted
artifacts, and use port 7860. A Git push alone does not supply the ignored
model files. The recorded deployment checks cover the native VM, not a
completed Docker build or Space deployment.

## Native service and HTTPS

The recorded installation uses systemd and Nginx on a shared Lightsail VM.
These files define the serving configuration:

| File | Purpose |
| --- | --- |
| [variant-screener.service](../deploy/variant-screener.service) | Dedicated user/group, one worker on `127.0.0.1:7860`, concurrency limit 16, restart on failure and thread limits |
| [requirements-runtime.lock](../deploy/requirements-runtime.lock) | Packages recorded on Ubuntu 24.04 / Python 3.12 on 24 October |
| [nginx.conf](../deploy/nginx.conf) | Recorded hostname, HTTPS certificate paths, HTTP redirect and ACME challenge route |
| [nginx.conf.example](../deploy/nginx.conf.example) | HTTP bootstrap template for another hostname |
| [renewal-reload-nginx.sh](../deploy/renewal-reload-nginx.sh) | Validates and reloads Nginx after successful certificate renewal |

For another release on that host:

1. Create `/opt/variant-screener/releases/<release>` with runtime source,
   matching trusted artifacts, deployment files and optional heatmaps.
2. Create its `.venv` on the host and install
   `deploy/requirements-runtime.lock`. Verify compatibility on another
   Python/platform; do not copy a development virtualenv between machines.
3. Precreate `data/raw`, `data/processed`, `data/external`, `outputs/figures`
   and `outputs/models`. Configuration import ensures these directories.
   The `variant-screener` account needs source/model read access and directory
   traversal; precreating the directories permits read-only source/model files.
4. Run the candidate as that account on another loopback port with strict
   mode and thread limits. Smoke-check it and inspect model metadata, then
   stop the temporary candidate.
5. Record the existing `current` symlink target, switch it to the verified
   release, and restart `variant-screener`. Check loopback and public HTTPS.
   Retain the preceding release for rollback.

The service sets `MemoryMax=768M`, `CPUQuota=100%` and `TasksMax=128`.
Inspect current capacity before adjusting them. A changed unit requires
`sudo systemctl daemon-reload` before restart. To roll back a full release,
restore the previous `current` target, restart and repeat verification.

Keep the app port on loopback behind a dedicated HTTPS virtual host.
Preserve the shared host's other routes. The supplied Nginx config forwards
`Host` and `X-Forwarded-*`, limits request bodies to 64 KiB and sets a
30-second proxy timeout. Replace its hostname and certificate paths for
another server. Validate with `nginx -t` before reload and keep port 80's
ACME challenge path reachable.

```sh
readlink -f /opt/variant-screener/current
sudo systemctl status variant-screener
sudo journalctl -u variant-screener -n 100 --no-pager
sudo systemctl restart variant-screener
sudo nginx -t
sudo systemctl status certbot.timer
sudo certbot certificates
sudo certbot renew --cert-name malaria-sickle-screener --dry-run --run-deploy-hooks --no-random-sleep-on-renew
```

Certificate keys and ACME account data remain under `/etc/letsencrypt` and
must stay outside source archives.

### Static-only updates

The source index references `style.css` and `script.js`. The recorded server
publication used versioned filenames; no repository build step generates
them. Upload matching assets first, verify checksums, then atomically replace
the index. Preserve the old index and its assets for cached clients and
rollback. Static-only updates do not reload the model.

The latest recorded index backup is
`/opt/variant-screener/ui-backups/gene-ui-21ae178287fc/`. After checking that
the backup and its referenced assets still exist, restore the preceding UI:

```sh
sudo cp /opt/variant-screener/ui-backups/gene-ui-21ae178287fc/index.html /opt/variant-screener/current/webapp/static/index.rollback.new
sudo mv /opt/variant-screener/current/webapp/static/index.rollback.new /opt/variant-screener/current/webapp/static/index.html
```

This restores HTML only. Check the active release before using an old backup.

## Verification

Run the existing regression checks in a development environment:

```sh
python -m pip install -r requirements.txt
python -m pip install pytest httpx
python -m pytest -q
node --test tests/test_ui.mjs
```

No npm installation is needed. For a running real-data model:

```sh
python3 scripts/smoke_deployment.py --base-url http://127.0.0.1:7860
python3 scripts/smoke_deployment.py --base-url https://malaria-sickle-screener.13-62-14-125.sslip.io
```

The smoke script checks health/metadata, 136 valid predictions, 19 invalid
requests, static/OpenAPI responses, structure metadata and optional heatmap
availability. It requires real provenance and accepts absent heatmaps.
It does not load external browser structures or measure concurrent capacity.
Also check the browser's five gene records, predictions, residue controls,
keyboard focus, desktop/mobile layout and optional viewer failure behavior.

For a read-only Linux host snapshot:

```sh
sh scripts/check_vm_capacity.sh
# Or use an already authorized SSH connection:
ssh user@server 'sh -s' < scripts/check_vm_capacity.sh
```

Compare available memory/disk, listening ports and process usage with
representative traffic. More workers duplicate the runtime and model in
memory. Historical serial timings are in [Deployment history](DEPLOYMENT_HISTORY.md);
model evaluation is documented in [Evaluation](EVALUATION.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing-model startup error | Supply the trusted pickle at `outputs/models/variant_screener_v1.pkl` in the release/image. |
| Artifact loading error | Verify artifact integrity and its scikit-learn version; a corrupt pickle does not trigger a demo. |
| Provenance rejected | Use a real-feature bundle; changing the metadata sidecar does not change provenance. |
| Health OK, interface demo/unverified | Inspect `demo_mode`, `data_provenance` and `/api/model-info`. |
| ACKR1 request fails | Use the API key `DARC`. |
| Heatmap 404 | Generate and copy the gene's optional JSON. |
| Viewer unavailable | Check WebGL and access to the three external viewer/structure domains. |
| Prediction 422 | Check the [API](API.md) fields and numeric bounds. |
| Proxy 502 or worker restarts | Check logs, listener port, model loading and memory limits. |
| 503 under concurrent load | Inspect load and latency against the worker's concurrency limit of 16. |
| Stale CSS/JS | Check the index's filenames and matching uploaded assets. |
