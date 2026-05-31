# TODO — Phase 2 (Reproducible pipeline + popEVE-like UI upgrade)

## Phase 2.1 — Reproducible pipeline runner
- [ ] Add a single CLI entrypoint (e.g., `src/pipeline/run_pipeline.py`) that runs in order:
  - [ ] `src/data/download.py`
  - [ ] `src/data/build_features.py`
  - [ ] `src/models/train.py`
  - [ ] `src/models/evaluate.py`
- [ ] Ensure runner prints artifact locations under `outputs/`.
- [ ] Add a `--skip-download/--skip-features/--skip-train` set of flags.

## Phase 2.2 — Canonical feature schema contract
- [ ] Extend the model bundle metadata with:
  - [ ] `feature_names`
  - [ ] `feature_order_version`
  - [ ] expected input schema (names + order)
- [ ] Update `src/ui/app.py` to assemble the model input vector using the saved `feature_names` order (no hardcoded column ordering).
- [ ] Add a UI-side validation that fails loudly if any expected feature is missing.

## Phase 2.3 — UI upgrade (popEVE-like, with 3D structure viewer)
- [ ] Keep Gradio app shell; embed a JS 3D viewer (recommended: NGL or 3Dmol.js) via `gr.HTML`.
- [ ] Add UI controls:
  - [ ] protein accession input (e.g., NP_000005-3)
  - [ ] structure source toggles: AlphaFold vs PDB (and user toggle supports both)
  - [ ] variant residue/position input and label display
- [ ] Add color-coding overlays + labels (residue/position + gene context).
- [ ] Add an explanation panel that ties 3D view selections to model features.

## Phase 2.4 — Test/verification
- [ ] Add/extend tests to verify:
  - [ ] UI input vector matches training feature order
  - [ ] pipeline runner produces expected artifacts

## Phase 2.5 — Deployment prep
- [ ] Confirm `src/ui/app.py` can run on Spaces with minimal local files (model + meta must be shipped or downloaded).
- [ ] Document run/deploy steps in README (Phase 2).

