# Optional ESM2 substitution maps

Reviewed on 30 October 2026 against `scripts/compute_heatmap.py` and the
served frontend. The **Amino acid substitutions** panel is independent of
the classifier. No precomputed maps are included in a clean clone because
`data/` is gitignored. This tracked guide replaces the operational reference
previously stored only in the ignored `data/heatmaps/README.md`.

## Generate

Run from the repository root in an environment with the optional dependencies:

```bash
python -m pip install -r scripts/requirements-heatmap.txt
python scripts/compute_heatmap.py --gene HBB
# Alternatively, process every supported gene:
python scripts/compute_heatmap.py --all
```

`--all` processes HBB, HBA1, HBA2, G6PD and DARC. Use `DARC` for ACKR1.
Each run fetches the canonical sequence from `rest.uniprot.org`; model weights
are downloaded from Hugging Face and can then use its local cache. The default
checkpoint is `facebook/esm2_t12_35M_UR50D` and the default device is `cpu`.

```bash
python scripts/compute_heatmap.py --gene G6PD --model facebook/esm2_t30_150M_UR50D --device cuda
```

CUDA requires a compatible local PyTorch/GPU setup. Runtime and memory depend
on the checkpoint, sequence length and hardware. The script makes a model
forward pass for each sequence position and overwrites the selected gene's
existing output. Preserve earlier files if needed for comparison.
Heatmap dependencies are not required by the serving app.

## Files and scores

Output is `data/heatmaps/<GENE>.json`, with these fields:

| Field | Contents |
| --- | --- |
| `gene` | App gene key |
| `uniprot` | Sequence accession: HBB P68871, HBA1/HBA2 P69905, G6PD P11413, DARC Q16570 |
| `sequence` | Downloaded canonical amino-acid sequence |
| `model` | Hugging Face checkpoint name |
| `method` | `esm2-masked-marginal` |
| `positions` | Array of `{ "pos": 1, "wt": "M", "effects": { ... } }`, with scores for all 20 standard amino acids |

`pos` is 1-based within the fetched sequence. At each position, the script
masks the wild-type residue and computes
`log P(mutant | masked sequence) - log P(wild type | masked sequence)`.
Scores are rounded to four decimals. Wild type has score zero; negative
values mean the substitution is less favored by this checkpoint in that
sequence context. These are not probabilities or clinically validated
pathogenicity labels. They are separate from the forest and are not popEVE
outputs.

The display colors clamp scores to −10 through 0: stronger negative values
are darker red; zero and positive scores share the light end. Selecting a
column lists finite scores in ascending order. The frontend accepts the older
`scores` field as well as the current `effects` field. Sequence positions are
not mapped to PDB chain numbering, and clicking the map does not change the
prediction inputs or viewer selection.

## Serve and check

```bash
curl --fail http://127.0.0.1:8000/api/heatmap/HBB
```

The API reads the file per request, so local JSON changes do not require a
model restart; reselect the gene or reload the browser to fetch them. A Docker
image copies maps at build time, so copied files require rebuilding/recreating
the container unless supplied through a separately configured mount.

The API returns 404 when a map is absent. The frontend hides the panel for a
missing or failed map request; no synthetic map is substituted. The server
does not validate map contents against the sequence/model. Keep source
accession, checkpoint and any local file hashes alongside feedback requiring
reproducibility: the JSON does not record a generation timestamp or source
release revision. See [deployment](DEPLOYMENT.md) for packaging and
[usage](USAGE.md) for the interface.
