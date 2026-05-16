# Data Sources — Download Instructions

All data used in this project is publicly available and free. No paid subscriptions required.

---

## 1. ClinVar (variant pathogenicity labels)

**What it provides**: The ground-truth labels for training — which variants are pathogenic and which are benign.

**Automated download**:
```bash
python src/data/download.py --dataset clinvar
```

**Manual download** (if script fails):
```
URL: https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
Save to: data/raw/variant_summary.txt.gz
Then: gunzip data/raw/variant_summary.txt.gz
```

**NCBI API key** (optional but recommended):
1. Go to https://www.ncbi.nlm.nih.gov/account/
2. Register with your email
3. Settings → API Key Management → Generate key
4. Add to `.env` as `NCBI_API_KEY=...`
5. With key: 10 requests/sec. Without: 3 requests/sec.

**Expected size**: ~800 MB uncompressed
**Key columns**: GeneSymbol, ClinicalSignificance, Chromosome, PositionVCF, ReferenceAlleleVCF, AlternateAlleleVCF

---

## 2. 1000 Genomes Project — Sample Panel

**What it provides**: Population labels (which sample = which population, e.g., YRI=Yoruba, GWD=Gambian). Used to identify West African samples.

**Automated download**:
```bash
python src/data/download.py --dataset 1kg
```

**Manual download**:
```
URL: ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/integrated_call_samples_v3.20130502.ALL.panel
Save to: data/raw/1kg_panel.tsv
```

**No account required.**
**Size**: ~1 MB

**West African populations in this dataset**:
| Code | Population | Country |
|------|-----------|---------|
| YRI | Yoruba | Nigeria |
| ESN | Esan | Nigeria |
| MSL | Mende | Sierra Leone |
| GWD | Gambian Western Division | Gambia |
| LWK | Luhya | Kenya |

---

## 3. MalariaGEN Pf7 — Ghana Malaria Genomics

**What it provides**: ~20,000 *Plasmodium falciparum* genomes from Africa, including ~400–600 from Ghana specifically. The most Ghana-specific public genomic data available.

**This requires manual registration (1–2 days for approval):**

1. Go to https://malariagen.net/data/pf7
2. Click "Apply for access" — fill in your name, institution (your school), and intended use
3. After approval, log in and download:
   - `pf7_samples.txt` → save to `data/raw/pf7_samples.txt`
   - Per-chromosome VCFs (start with chr11 for HBB) → `data/raw/pf7_chr11.vcf.gz`

**Size**: Full dataset ~5 GB. Ghana subset only ~200 MB.
**No cost.**

**What to write in the application form**:
> "High school research project investigating pathogenic variant classification in West African populations, with focus on malaria-resistance genes (HBB, G6PD). Data will be used only for computational analysis."

---

## 4. CADD Scores — Variant Deleteriousness

**What it provides**: A score (0–60+) for how likely each variant is to disrupt protein function. One of the most important features.

**No registration needed.** Public API, rate-limited to 1 request/second.

**API format**:
```
GET https://cadd.gs.washington.edu/api/v1.0/{chr}:{pos}_{ref}_{alt}
Example: https://cadd.gs.washington.edu/api/v1.0/11:5246696_A_T
```

The `build_features.py` script queries this automatically and caches results in `data/external/cadd_cache.json` so you never re-query the same variant twice.

**Alternative — bulk download** (if you have many variants):
```
URL: https://krishna.gs.washington.edu/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz
Warning: This file is ~80 GB. Use the API instead.
```

---

## 5. gnomAD — Population Allele Frequencies

**What it provides**: AFR (African) allele frequency for each variant — the PRIMARY feature distinguishing your model from population-agnostic tools.

**No registration or API key needed.** Public GraphQL API.

**API endpoint**: `https://gnomad.broadinstitute.org/api`

**Example query**:
```graphql
{
  variant(variantId: "11-5246696-A-T", dataset: gnomad_r4) {
    genome {
      populations {
        id
        ac
        an
      }
    }
  }
}
```

The `build_features.py` script handles all gnomAD queries automatically.

**Alternative — browser lookup**:
Go to https://gnomad.broadinstitute.org and search any variant to see population frequencies interactively.

---

## 6. UCSC Genome Browser — Conservation Scores (Optional)

**What it provides**: phyloP conservation scores — how conserved a genomic position is across species (positive = conserved = more likely functional).

**Access**:
- Browser: https://genome.ucsc.edu/
- Tables: https://genome.ucsc.edu/cgi-bin/hgTables
- API: https://api.genome.ucsc.edu/getData/track?genome=hg38&track=phyloP100way&chrom=chr11&start=5246695&end=5246696

**Note**: The current implementation uses CADD score as a conservation proxy. If you want real phyloP scores, query the UCSC API per variant and replace `conservation_phylop` in the feature matrix.

---

## Summary Table

| Dataset | Script | Account needed | Size | Time |
|---|---|---|---|---|
| ClinVar | `download.py --dataset clinvar` | Optional (NCBI key) | 800 MB | 5 min |
| 1000 Genomes panel | `download.py --dataset 1kg` | No | 1 MB | <1 min |
| MalariaGEN Pf7 | Manual | Yes (free) | 200 MB–5 GB | 1–2 days (approval) |
| CADD | Auto in `build_features.py` | No | Cached locally | Per variant |
| gnomAD | Auto in `build_features.py` | No | API only | Per variant |
| UCSC phyloP | Optional API | No | API only | Per variant |

---

## Data directory structure after download

```
data/
├── raw/
│   ├── variant_summary.txt          ← ClinVar (800 MB)
│   ├── 1kg_panel.tsv                ← 1000 Genomes panel (1 MB)
│   └── pf7_samples.txt              ← MalariaGEN (manual download)
├── processed/
│   ├── clinvar_clean.csv            ← generated by parse_clinvar.py
│   └── features.csv                 ← generated by build_features.py
└── external/
    └── cadd_cache.json              ← CADD API cache (grows over time)
```
