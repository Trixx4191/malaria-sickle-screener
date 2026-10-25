# Gene reference data

The locus strip uses Ensembl release 116 and the GRCh38 human reference
assembly, verified on 25 October 2026. Coordinates are 1-based and inclusive.
They describe complete annotated gene spans, not a submitted variant,
transcript, coding sequence, or exon structure. These fields provide context
and are not inputs to the pathogenicity model.

| App key | Approved symbol | Chromosome | Start | End | Strand | Cytoband |
| --- | --- | --- | ---: | ---: | --- | --- |
| HBB | HBB | 11 | 5,225,464 | 5,229,395 | Reverse | 11p15.4 |
| G6PD | G6PD | X | 154,517,825 | 154,547,584 | Reverse | Xq28 |
| DARC | ACKR1 | 1 | 159,204,568 | 159,206,500 | Forward | 1q23.2 |
| HBA1 | HBA1 | 16 | 176,660 | 177,527 | Forward | 16p13.3 |
| HBA2 | HBA2 | 16 | 172,021 | 173,910 | Forward | 16p13.3 |

The application retains `DARC` as its API key. The interface identifies it as
`ACKR1 (DARC)` because ACKR1 is the approved symbol and DARC is a previous
approved symbol. See the [HGNC ACKR1 record](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4035).

The chromosome track locates the selected gene across the full chromosome.
Its marker is enlarged to remain visible. The chromosome lengths are:

| Chromosome | Length in bases |
| --- | ---: |
| 1 | 248,956,422 |
| 11 | 135,086,622 |
| 16 | 90,338,345 |
| X | 156,040,895 |

Primary gene records:

- [HBB](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000244734)
- [G6PD](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000160211)
- [ACKR1](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000213088)
- [HBA1](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000206172)
- [HBA2](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000188536)

The frontend stores this small reference set in `GENE_CONTEXT` in
`webapp/static/script.js`, so selecting a gene does not depend on a live
Ensembl request. Update the coordinates, assembly label, chromosome lengths,
and this reference together when changing annotation releases. Do not mix
gene boundaries from different annotation providers.
