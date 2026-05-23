# Changelog

All notable changes to this project are documented in this file.
Format: [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-05-22

### Added

**Dataset**
- 10 human-reviewed, validated records covering: nusinersen, onasemnogene
  abeparvovec, ivacaftor, migalastat, lonafarnib, vutrisiran, givosiran,
  risdiplam, exagamglogene autotemcel, inclisiran
- 50-drug seed list (`data/seeds/drug_seeds.json`) spanning ASO, siRNA, gene
  therapy, enzyme replacement, chaperone, CFTR modulator, monoclonal antibody,
  inhibitor, and agonist mechanism classes
- Frozen release artefacts at `data/releases/v0.1.0/`:
  `triples.jsonl`, `triples.csv`, `triples.parquet`
- `data/DATASET_CARD.md` (Hugging Face–style dataset card with per-row
  provenance, known biases, suggested uses, BibTeX citation)

**ETL Pipeline**
- Fetch layer: OpenFDA and DailyMed clients with rate limiting and local caching
- Extract layer: Claude tool-use structured extraction (`PROMPT_VERSION=v1.2.0`,
  `MODEL=claude-sonnet-4-6`)
- Validate layer: ChEMBL + DrugBank cross-validation; typer+rich interactive
  reviewer CLI (`fda-review`)
- Export layer: JSONL, flat CSV, and Hugging Face Datasets parquet

**Public Python API**
- `from fda_strategy_triples import load_dataset` — returns `pd.DataFrame` or
  `list[ExtractedTriple]`; supports `version=` and `as_pydantic=` parameters
- Bundled release data as package data (accessible after `pip install`)

**Packaging**
- `pyproject.toml` with full PyPI classifiers, GPL-3.0 code license, CC-BY-4.0
  dataset license
- `CITATION.cff` for GitHub "Cite this repository" rendering
- `datasets/hf_repo/` skeleton for Hugging Face Hub publication
- `Makefile` with `publish-hf` target
- `tests/test_loader.py` verifying the public loader API contract

### Schema

```
ExtractedTriple
  triple: FDATriple
    drug_name_generic | drug_name_brand | approval_date | indicated_disease
    associated_genes  | variant_context | molecular_target
    mechanism_class   | mechanism_summary | primary_citation_pmid
  metadata: ValidationMetadata
    source_apis | fetch_timestamp | prompt_version | extractor_model
    chembl_validated | drugbank_validated | discrepancies
    reviewer | reviewed_at | validated
  raw_label_url | confidence_score | id | schema_version
```

### Known limitations

- 10 of 50 seed drugs validated; remaining 40 require human review
- `Ekterly` drug identity unconfirmed — flagged `needs_manual_verification=True`
- BRD4780 is investigational (not FDA-approved)
- voxelotor (Oxbryta) withdrawn from market 2024-09-25; included for historical completeness
- PMIDs for exagamglogene autotemcel and vutrisiran carry a librarian-verification note

---

## [Unreleased]

### Planned for v0.2.0
- Complete the 50-seed validation pass
- Add ClinVar accession cross-links for each `variant_context`
- Zenodo DOI registration and CITATION.cff update

### Planned for v0.3.0
- Next 50 drugs from Orphanet prevalence-ranked list
- EMA-only approvals (EU-labelled where no FDA equivalent)
- Structured variant ontology (SO term per variant class)
