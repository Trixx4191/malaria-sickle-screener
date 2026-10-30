# Gene and protein reference data

The locus strip uses a static Ensembl release 116 reference set for the
GRCh38 human assembly, recorded on 25 October 2026.

Coordinates are 1-based and inclusive. They describe complete annotated
gene spans, not a submitted variant, transcript, coding sequence, or exon
structure. The chromosome track locates the selected gene across the full
chromosome; its marker is enlarged for visibility. These fields provide
context and do not enter the classifier.

| App/API key | Displayed symbol | Chromosome | Start | End | Strand | Cytoband |
| --- | --- | --- | ---: | ---: | --- | --- |
| HBB | HBB | 11 | 5,225,464 | 5,229,395 | Reverse | 11p15.4 |
| G6PD | G6PD | X | 154,517,825 | 154,547,584 | Reverse | Xq28 |
| DARC | ACKR1 (DARC) | 1 | 159,204,568 | 159,206,500 | Forward | 1q23.2 |
| HBA1 | HBA1 | 16 | 176,660 | 177,527 | Forward | 16p13.3 |
| HBA2 | HBA2 | 16 | 172,021 | 173,910 | Forward | 16p13.3 |

The dropdown names the DARC option `ACKR1`; the selected-gene strip and
result labels use `ACKR1 (DARC)`. Requests and cached heatmap filenames must
still use `DARC`. The prediction API does not accept `ACKR1` as an alias.
The naming reference is the [HGNC ACKR1 record](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4035).

| Chromosome | Length in bases |
| --- | ---: |
| 1 | 248,956,422 |
| 11 | 135,086,622 |
| 16 | 90,338,345 |
| X | 156,040,895 |

The frontend stores these values in `GENE_CONTEXT` in
`webapp/static/script.js`; selecting a gene does not require a live Ensembl
request. The reference links open these records:

- [HBB, ENSG00000244734](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000244734)
- [G6PD, ENSG00000160211](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000160211)
- [ACKR1, ENSG00000213088](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000213088)
- [HBA1, ENSG00000206172](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000206172)
- [HBA2, ENSG00000188536](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000188536)

External record pages can change independently of the locally stored
release. When changing annotation releases, update the gene coordinates,
assembly and release labels, chromosome lengths, initial HBB HTML values,
frontend checks, and this reference together. Do not mix boundaries from
different annotation providers.

## Protein structures and substitution sequences

The following records are configured in
`webapp/model_service.py::STRUCTURE_REGISTRY` and
`scripts/compute_heatmap.py::GENE_UNIPROT`:

| App key | Viewer structure | Selected chain | Source | Heatmap UniProt accession |
| --- | --- | --- | --- | --- |
| HBB | `2HHB` | B | Experimental PDB | `P68871` |
| HBA1 | `2HHB` | A | Experimental PDB | `P69905` |
| HBA2 | `2HHB` | A | Experimental PDB | `P69905` |
| G6PD | `2BH9` | A | Experimental PDB | `P11413` |
| DARC | `AF-Q16570-F1` | A | AlphaFold prediction | `Q16570` |

The viewer displays reference structures, not simulated mutants. Coverage
depends on the selected record. DARC uses the configured AlphaFold model;
HBA1 and HBA2 share a structure and heatmap accession.

`GET /api/structure/{gene}` returns the registry record; the browser then
loads the coordinate file from RCSB, or discovers the current AlphaFold
file through the AlphaFold API. The browser also loads 3Dmol.js from
`3dmol.org`. The app server does not bundle those remote structures or
the viewer library. Network failures can prevent the optional viewer from
loading while annotation scoring continues. See [usage](USAGE.md) and
[deployment](DEPLOYMENT.md) for the runtime behavior.

Residue selection uses the loaded structure's residue numbers and selected
chain. Heatmap positions are 1-based indices of the fetched canonical
UniProt sequence. These numbering systems are not automatically aligned;
processing, missing residues, and structure-specific numbering can matter.
The viewer neither maps genomic coordinates to residues nor changes the
classifier input when a residue is selected. Preset residue highlights are
illustrations, not retrieved variant annotations.

The cartoon uses the PyMOL secondary-structure palette: helices red,
beta sheets yellow, and loops/coils green. Other chains are faded; the
selected residue uses atom colors. The tier colors in the score panel do
not recolor the protein. Downloading the PDB saves the loaded reference
coordinate file, not a simulated mutant structure or prediction report.

Optional ESM2 substitution matrices use the configured UniProt sequences
and are served from `data/heatmaps/<APP_KEY>.json`. Their scores are separate
from the classifier and do not establish clinical pathogenicity. Generation,
cache schema, and interpretation are documented in [HEATMAPS.md](HEATMAPS.md).

Training coverage and evaluation limits are documented in
[EVALUATION.md](EVALUATION.md); feature construction is in [DATA.md](DATA.md).
