"""
compute_heatmap.py — generate a per-position x per-substitution effect matrix
for a gene, using ESM2 zero-shot mutation scoring (masked-marginal method).

Uses a pretrained protein language model with a forward pass per position.
The outputs are ESM2 sequence scores, not EVE/popEVE outputs or calibrated
pathogenicity probabilities. They do not enter the web classifier.

Implemented masked-marginal method:
  For each position i in the sequence:
    1. Replace residue i with the [MASK] token.
    2. Run the model, read the log-probabilities over the vocabulary at
       position i.
    3. score(i, mutant_aa) = log P(mutant_aa | masked seq) - log P(wt_aa | masked seq)
  A negative score means the substitution is less favored than WT by this
  checkpoint in the masked sequence context. It is not a clinical label.

This does NOT require internet access at query time — it's a one-time,
per-gene precompute. Run it once per gene; the FastAPI backend just serves
the cached JSON from data/heatmaps/<GENE>.json. Sequence positions are not
automatically mapped to structure residue numbers. See docs/HEATMAPS.md.

Usage:
    pip install -r scripts/requirements-heatmap.txt
    python scripts/compute_heatmap.py --gene HBB
    python scripts/compute_heatmap.py --gene HBB --model facebook/esm2_t12_35M_UR50D
    python scripts/compute_heatmap.py --all

Requires internet access to:
  - rest.uniprot.org        (fetch the canonical protein sequence)
  - huggingface.co          (download the ESM2 model weights, first run only;
                             cached locally afterwards)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "heatmaps"

# UniProt accessions for the genes this tool covers. Kept in sync with
# src/utils/config.py::TARGET_GENES and model_service.py::STRUCTURE_REGISTRY.
GENE_UNIPROT = {
    "HBB": "P68871",
    "HBA1": "P69905",
    "HBA2": "P69905",
    "G6PD": "P11413",
    "DARC": "Q16570",
}

AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")


def fetch_sequence(uniprot_accession: str) -> str:
    """Pull the canonical protein sequence straight from UniProt (FASTA)."""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_accession}.fasta"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    lines = resp.text.strip().splitlines()
    seq = "".join(line.strip() for line in lines if not line.startswith(">"))
    if not seq:
        raise ValueError(f"Got an empty sequence back for {uniprot_accession}")
    return seq


def compute_masked_marginal_matrix(sequence: str, model_name: str, device: str = "cpu"):
    """
    Returns a list of {pos, wt, effects: {AA: score}} — 1-indexed positions,
    scores are log P(mutant) - log P(wt) at that position under the model.
    """
    import torch
    from transformers import AutoTokenizer, AutoModelForMaskedLM

    print(f"Loading {model_name} ...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForMaskedLM.from_pretrained(model_name)
    model.to(device)
    model.eval()

    mask_token_id = tokenizer.mask_token_id
    aa_token_ids = {aa: tokenizer.convert_tokens_to_ids(aa) for aa in AMINO_ACIDS}

    base_ids = tokenizer(sequence, return_tensors="pt")["input_ids"][0]
    # ESM tokenizers add a leading <cls> and trailing <eos>; residue i of the
    # sequence (0-indexed) lands at token index i+1.
    offset = 1

    results = []
    t0 = time.time()
    with torch.no_grad():
        for i, wt_aa in enumerate(sequence):
            ids = base_ids.clone()
            ids[i + offset] = mask_token_id
            logits = model(ids.unsqueeze(0).to(device)).logits[0, i + offset]
            log_probs = torch.log_softmax(logits, dim=-1)

            wt_id = aa_token_ids.get(wt_aa)
            wt_logprob = log_probs[wt_id].item() if wt_id is not None else None

            effects = {}
            for aa in AMINO_ACIDS:
                aa_id = aa_token_ids[aa]
                mut_logprob = log_probs[aa_id].item()
                effects[aa] = round(
                    mut_logprob - wt_logprob if wt_logprob is not None else mut_logprob, 4
                )

            results.append({"pos": i + 1, "wt": wt_aa, "effects": effects})

            if (i + 1) % 50 == 0 or i == len(sequence) - 1:
                elapsed = time.time() - t0
                print(f"  {i + 1}/{len(sequence)} positions scored ({elapsed:.1f}s)", file=sys.stderr)

    return results


def compute_for_gene(gene: str, model_name: str, device: str = "cpu"):
    gene = gene.upper()
    if gene not in GENE_UNIPROT:
        raise ValueError(f"Unknown gene '{gene}'. Known genes: {list(GENE_UNIPROT)}")

    accession = GENE_UNIPROT[gene]
    print(f"[{gene}] fetching canonical sequence for {accession} from UniProt ...", file=sys.stderr)
    sequence = fetch_sequence(accession)
    print(f"[{gene}] sequence length: {len(sequence)} aa", file=sys.stderr)

    positions = compute_masked_marginal_matrix(sequence, model_name, device=device)

    payload = {
        "gene": gene,
        "uniprot": accession,
        "sequence": sequence,
        "model": model_name,
        "method": "esm2-masked-marginal",
        "positions": positions,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{gene}.json"
    out_path.write_text(json.dumps(payload))
    print(f"[{gene}] wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gene", help="Gene symbol, e.g. HBB")
    parser.add_argument("--all", action="store_true", help="Compute for every gene in GENE_UNIPROT")
    parser.add_argument(
        "--model",
        default="facebook/esm2_t12_35M_UR50D",
        help="Hugging Face ESM2 checkpoint. Default: facebook/esm2_t12_35M_UR50D; "
             "larger checkpoints require more memory and compute.",
    )
    parser.add_argument("--device", default="cpu", help="'cpu' or 'cuda'")
    args = parser.parse_args()

    if not args.gene and not args.all:
        parser.error("Pass --gene HBB or --all")

    genes = list(GENE_UNIPROT) if args.all else [args.gene]
    for gene in genes:
        compute_for_gene(gene, args.model, device=args.device)


if __name__ == "__main__":
    main()
