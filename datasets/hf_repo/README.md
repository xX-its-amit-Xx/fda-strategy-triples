---
license: cc-by-4.0
task_categories:
  - text-classification
  - question-answering
language:
  - en
tags:
  - biology
  - pharmacology
  - rare-disease
  - FDA
  - genomics
  - drug-mechanism
  - gene-therapy
  - antisense
  - siRNA
  - pharmacogenomics
size_categories:
  - n<1K
pretty_name: "FDA Strategy Triples"
dataset_info:
  features:
    - name: id
      dtype: string
    - name: drug_name_generic
      dtype: string
    - name: drug_name_brand
      dtype: string
    - name: approval_date
      dtype: string
    - name: indicated_disease
      dtype: string
    - name: associated_genes
      sequence: string
    - name: variant_context
      dtype: string
    - name: molecular_target
      dtype: string
    - name: mechanism_class
      dtype:
        class_label:
          names:
            '0': inhibitor
            '1': agonist
            '2': chaperone
            '3': ASO
            '4': siRNA
            '5': gene_therapy
            '6': enzyme_replacement
            '7': monoclonal_antibody
            '8': modulator
            '9': other
    - name: mechanism_summary
      dtype: string
    - name: primary_citation_pmid
      dtype: string
    - name: reviewer
      dtype: string
    - name: reviewed_at
      dtype: string
    - name: validated
      dtype: bool
    - name: prompt_version
      dtype: string
    - name: extractor_model
      dtype: string
  splits:
    - name: train
      num_examples: 10
---

# Dataset Card: FDA Strategy Triples

**Version:** 0.1.0 | **Records (validated):** 10 | **Seed drugs:** 50

A curated, human-reviewed dataset of **(gene → variant_context → FDA-approved drug → molecular_target → mechanism)** tuples for rare diseases.

## Quick Start

```python
# Option A — Hugging Face Datasets
from datasets import load_dataset
ds = load_dataset("your-hf-username/fda-strategy-triples")
df = ds["train"].to_pandas()

# Option B — pip install (includes frozen parquet)
pip install fda-strategy-triples

from fda_strategy_triples import load_dataset
df = load_dataset()
print(df[["drug_name_generic", "mechanism_class", "associated_genes"]])
```

## What's in Each Row?

Every record answers: *"For a patient with **this gene variant**, what **FDA-approved drug** is available, what does it target, and how does it work?"*

| Field | Example |
|---|---|
| `drug_name_generic` | `ivacaftor` |
| `drug_name_brand` | `Kalydeco` |
| `indicated_disease` | `Cystic fibrosis with CFTR gating mutations` |
| `associated_genes` | `["CFTR"]` |
| `variant_context` | `G551D (c.1652G>A, p.Gly551Asp) gating mutation` |
| `molecular_target` | `P13569 (CFTR)` |
| `mechanism_class` | `modulator` |
| `mechanism_summary` | `Ivacaftor is a CFTR channel potentiator that…` |
| `primary_citation_pmid` | `21083385` |

## Dataset Description

`fda-strategy-triples` pairs rare-disease genetics with FDA-approved pharmacology.
The pipeline fetches structured product labels from **OpenFDA** and **DailyMed**,
extracts mechanistic fields with **Claude** (Anthropic, tool-use structured output),
cross-checks against **ChEMBL** and **DrugBank**, and requires **human expert review**
before any record enters the validated dataset.

### Mechanism Classes

`inhibitor` · `agonist` · `chaperone` · `ASO` · `siRNA` · `gene_therapy` ·
`enzyme_replacement` · `monoclonal_antibody` · `modulator` · `other`

### Therapeutic Areas (v0.1.0)

Spinal muscular atrophy, Duchenne muscular dystrophy, Cystic fibrosis, Fabry disease,
hATTR amyloidosis, ALS (SOD1), Sickle cell disease, Beta-thalassemia, Phenylketonuria,
Progeria, Acute hepatic porphyria, Familial hypercholesterolaemia, and more.

## Per-Row Provenance

Each record stores a complete extraction + review chain:

```
metadata.source_apis       → ["openfda", "dailymed"]
metadata.fetch_timestamp   → "2025-01-15T00:00:00Z"
metadata.prompt_version    → "v1.2.0"
metadata.extractor_model   → "claude-sonnet-4-6"
metadata.chembl_validated  → true / false
metadata.drugbank_validated→ true / false
metadata.discrepancies     → ["..."]   (empty = no mismatches)
metadata.reviewer          → "shenoy.am@husky.neu.edu"
metadata.reviewed_at       → "2025-02-01T12:00:00Z"
metadata.validated         → true   (required for inclusion)
```

## Known Biases

- **Drug-class skew**: RNA therapies (ASO + siRNA) ~30% of records
- **Population skew**: Indicated diseases skew toward Mendelian disorders with European-ancestry prevalence (e.g. classic PKU, HGPS, CF); sickle cell disease disproportionately affects individuals of African ancestry but SCD pivotal trials enrolled majority non-African participants
- **Geographic FDA bias**: All approval dates are US FDA; EMA-only drugs excluded

## Suggested Uses

1. **Drug-repurposing prior**: query `associated_genes` to find all approved drugs for a target gene
2. **Agent benchmark**: validated records as ground truth for gene→drug retrieval tasks
3. **Education**: mechanism diversity spanning 10 pharmacological classes
4. **Regulatory trend analysis**: `approval_date` + `mechanism_class` over time

## Citation

```bibtex
@dataset{shenoy2025fda_strategy_triples,
  author    = {Shenoy, Amit},
  title     = {{FDA Strategy Triples: A curated dataset of gene–variant–drug–target–mechanism associations for rare diseases}},
  year      = {2025},
  publisher = {GitHub},
  version   = {0.1.0},
  url       = {https://github.com/xX-its-amit-Xx/fda-strategy-triples},
  license   = {CC-BY-4.0}
}
```

## Source Code

[github.com/xX-its-amit-Xx/fda-strategy-triples](https://github.com/xX-its-amit-Xx/fda-strategy-triples) — GPL-3.0
