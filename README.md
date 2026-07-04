# fda-strategy-triples

> **A curated, human-reviewed dataset of (gene → variant\_context → FDA drug → molecular\_target → mechanism) tuples for rare diseases.**

[![License: GPL v3](https://img.shields.io/badge/Code-GPL%20v3-blue.svg)](LICENSE)
[![Dataset License: CC BY 4.0](https://img.shields.io/badge/Dataset-CC%20BY%204.0-green.svg)](DATASET_LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/fda-strategy-triples.svg)](https://pypi.org/project/fda-strategy-triples/)

## Install

```bash
pip install fda-strategy-triples
```

```python
from fda_strategy_triples import load_dataset
df = load_dataset()
print(df[["drug_name_generic", "mechanism_class", "associated_genes"]])
```

The frozen validated dataset ships inside the package — no API keys or internet
connection required to load it.

---

## What is this?

`fda-strategy-triples` pairs rare-disease genetics with FDA-approved pharmacology.
Each row answers: *"For a patient with **this gene variant**, what **drug** is approved,
what does it target at the molecular level, and how does it work?"*

The pipeline fetches structured product labels from public APIs (OpenFDA, DailyMed),
extracts mechanistic fields with Claude (structured tool-use output, Pydantic-validated),
cross-checks against ChEMBL and DrugBank, and requires **human expert review** before any
record enters the validated dataset.

---

## Sample Row

```json
{
  "id": "3f1a2b4c-0003-4e5f-8a9b-c1d2e3f40003",
  "schema_version": "1.0.0",
  "triple": {
    "drug_name_generic": "ivacaftor",
    "drug_name_brand": "Kalydeco",
    "approval_date": "2012-01-31",
    "indicated_disease": "Cystic fibrosis (CF) with CFTR gating mutations (G551D and other class III/IV variants)",
    "associated_genes": ["CFTR"],
    "variant_context": "G551D (c.1652G>A, p.Gly551Asp) gating mutation in CFTR and ≥11 other gating or residual-function mutations; not effective for F508del homozygous patients alone",
    "molecular_target": "P13569 (CFTR) — ATP-binding cassette transporter subfamily C member 7",
    "mechanism_summary": "Ivacaftor is a CFTR channel potentiator that binds to the membrane-spanning domains of CFTR and increases the open-channel probability of the defective protein, restoring chloride ion transport at the epithelial surface without correcting protein folding.",
    "mechanism_class": "modulator",
    "primary_citation_pmid": "21083385"
  },
  "metadata": {
    "source_apis": ["openfda", "dailymed"],
    "fetch_timestamp": "2025-01-15T00:00:00Z",
    "prompt_version": "v1.2.0",
    "extractor_model": "claude-sonnet-4-6",
    "chembl_validated": true,
    "drugbank_validated": true,
    "discrepancies": [],
    "reviewer": "shenoy.am@husky.neu.edu",
    "reviewed_at": "2025-02-01T12:00:00Z",
    "validated": true
  },
  "confidence_score": 0.98
}
```

---

## Coverage (v0.1.0)

| Stat | Value |
|---|---|
| Seed drugs | 50 |
| Validated records | 10 |
| Mechanism classes | 8 (ASO, siRNA, gene therapy, enzyme replacement, modulator, inhibitor, chaperone, monoclonal antibody) |
| Therapeutic areas | 12+ (SMA, DMD, CF, Fabry, hATTR, ALS, SCD, beta-thal, PKU, progeria, AHP, FH) |
| Genes covered | 28 |
| API snapshot date | 2025-01-15 |
| Prompt version | v1.2.0 |
| Extractor model | claude-sonnet-4-6 |

---

## Quickstart

```bash
# 1. Install
git clone https://github.com/xX-its-amit-Xx/fda-strategy-triples
cd fda-strategy-triples
pip install -e ".[dev]"

# 2. Set API keys
export ANTHROPIC_API_KEY=sk-ant-...   # required for extraction
export OPENFDA_API_KEY=...            # optional; lifts rate cap
export DRUGBANK_API_KEY=...           # optional; required for DrugBank cross-check

# 3. Run the pipeline (fetches, extracts, cross-checks)
python scripts/run_pipeline.py --limit 5   # dry-run on first 5 drugs

# 4. Review extractions interactively
fda-review start

# 5. Export validated data
fda-review export --csv data/validated/triples.csv
python -m fda_strategy_triples.export.to_hf_dataset
```

### Load the validated dataset directly (no pipeline needed)

```python
import json
from pathlib import Path

records = [
    json.loads(line)
    for line in Path("data/validated/validated_triples.jsonl").read_text().splitlines()
    if line.strip()
]

# Gene → drug lookup
gene_to_drugs = {}
for r in records:
    for gene in r["triple"]["associated_genes"]:
        gene_to_drugs.setdefault(gene, []).append(r["triple"]["drug_name_generic"])

print(gene_to_drugs["TTR"])
# → ['vutrisiran', 'givosiran', 'inotersen', 'inclisiran', ...]

# Filter by mechanism class
sirna_drugs = [
    r["triple"]["drug_name_generic"]
    for r in records
    if r["triple"]["mechanism_class"] == "siRNA"
]
print(sirna_drugs)
# → ['vutrisiran', 'givosiran', 'inclisiran', 'fitusiran']
```

### Load as a Hugging Face Dataset

```python
from datasets import load_from_disk

ds = load_from_disk("data/validated/hf_dataset")
print(ds["train"].features)
print(ds["train"][0])
```

---

## Architecture

```
data/seeds/drug_seeds.json          ← 50-drug seed list (genric, brand, ChEMBL ID, hints)
      │
      ▼
src/fda_strategy_triples/
  fetch/
    openfda.py   ← OpenFDA /drug/label.json  (rate-limited, cached)
    dailymed.py  ← DailyMed SPL v2 REST API  (rate-limited, cached)
    chembl.py    ← ChEMBL molecule + mechanism endpoint
    drugbank.py  ← DrugBank REST API (requires license key)
  extract/
    schema.py    ← Pydantic v2 models: FDATriple, ValidationMetadata, ExtractedTriple
    extractor.py ← Claude tool-use extraction (PROMPT_VERSION="v1.2.0")
  validate/
    cross_check.py   ← ChEMBL + DrugBank cross-validation, discrepancy logging
    reviewer_cli.py  ← typer + rich interactive review CLI
  export/
    to_jsonl.py      ← JSONL + flat CSV export
    to_hf_dataset.py ← Hugging Face Datasets parquet export
      │
      ▼
data/
  raw/       ← cached API responses (gitignored)
  extracted/ ← Claude extractions, unvalidated (gitignored)
  validated/ ← human-reviewed ✓ CHECKED INTO GIT ✓
```

---

## Reproducibility

| Component | Pinned value |
|---|---|
| API snapshot | 2025-01-15 |
| Extractor model | `claude-sonnet-4-6` |
| Prompt version | `v1.2.0` (see `extractor.py:PROMPT_VERSION`) |
| Schema version | `1.0.0` (see `schema.py:SCHEMA_VERSION`) |
| OpenFDA version | v1 (base URL: `https://api.fda.gov/drug/label.json`) |
| DailyMed API | v2 (base URL: `https://dailymed.nlm.nih.gov/dailymed/services/v2/`) |

To re-run extraction against the same label snapshots, check out this repo at the
`v0.1.0` tag and use the cached responses in `data/raw/` (download from release
artefacts — not committed due to size).

---

## Validation Policy

> Every record in `data/validated/` has been manually reviewed by a domain expert.
> Records in `data/extracted/` (gitignored) are LLM-generated and **must not** be
> used in downstream applications without further review.

Review criteria applied:
1. Gene symbol matches HGNC nomenclature
2. Variant context is quoted accurately from the SPL or well-established literature
3. UniProt accession is correct for the stated target
4. Mechanism summary survives a domain-expert audit
5. PMID resolves to the correct pivotal trial on PubMed

---

## Roadmap

| Milestone | Target |
|---|---|
| v0.1.0 | 10 validated records, pipeline scaffolding |
| v0.2.0 | 50 validated records (complete seed list) |
| v0.3.0 | Next 50 from Orphanet prevalence list + EMA-only approvals |
| v1.0.0 | 200 records; Hugging Face Hub release; structured variant ontology (ClinVar accession per variant\_context) |

Next 50 targets drawn from Orphanet prevalence-ranked list:
- Batten disease gene therapies (CLN3, CLN6, CLN7)
- GBA1-targeted therapies (eliglustat, miglustat, venglustat)
- NPC1 therapies (arimoclomol)
- Complement-mediated rare diseases (pegcetacoplan, iptacopan)
- Rare endocrine/metabolic (teprotumumab, setrusumab)

---

## Contributing

1. Open an issue to discuss a new drug seed or a correction
2. For extraction changes, bump `PROMPT_VERSION` and re-run affected records
3. All validated records require a domain-expert reviewer signature
4. Data corrections must be accompanied by a PMID or label URL

---

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
