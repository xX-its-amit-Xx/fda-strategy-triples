# Dataset Card: FDA Strategy Triples

**Version:** 0.1.0  
**License (dataset):** CC-BY-4.0 (see DATASET_LICENSE)  
**License (code):** GNU GPL 3.0 (see LICENSE)  
**Maintainer:** Amit Shenoy `<shenoy.am@husky.neu.edu>`  
**Last updated:** 2025-01-15  
**Records (validated):** 10 (seed target: 50)

---

## Dataset Description

`fda-strategy-triples` is a curated, human-reviewed dataset of
**(gene → variant\_context → FDA-approved drug → molecular\_target → mechanism)**
tuples for rare and ultra-rare diseases.  Every row encodes:

- The causal gene(s) and specific variant context defining patient eligibility
- The FDA-approved (or investigational) drug
- Its primary molecular target (UniProt accession when available)
- A 1–2 sentence mechanistic summary and controlled-vocabulary mechanism class
- Full provenance: which APIs were queried, which LLM prompt version was used,
  and who reviewed the record

The dataset covers antisense oligonucleotides (ASOs), siRNAs, gene therapies,
enzyme replacement therapies, pharmacological chaperones, CFTR modulators,
monoclonal antibodies, and other mechanism classes across 15+ therapeutic areas.

---

## Dataset Structure

### Data Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable UUID4 record identifier |
| `schema_version` | string | Pydantic schema version (e.g. `1.0.0`) |
| `drug_name_generic` | string | INN/USAN generic name (lowercase) |
| `drug_name_brand` | string | FDA proprietary/trade name |
| `approval_date` | string \| null | ISO 8601 FDA approval date, or `"investigational"` |
| `indicated_disease` | string | Primary rare-disease indication |
| `associated_genes` | list[string] | HGNC gene symbols |
| `variant_context` | string | Specific variant class / mutation context |
| `molecular_target` | string | Primary target; `UniProt_acc (SYMBOL)` when available |
| `mechanism_class` | enum | Controlled-vocabulary class (see below) |
| `mechanism_summary` | string | 1–2 sentence mechanistic description |
| `primary_citation_pmid` | string \| null | PubMed ID of pivotal trial |
| `source_apis` | list[string] | APIs queried (`openfda`, `dailymed`) |
| `fetch_timestamp` | string | ISO 8601 UTC timestamp of raw-data fetch |
| `prompt_version` | string | Extractor prompt version (e.g. `v1.2.0`) |
| `extractor_model` | string | Anthropic model ID used for extraction |
| `chembl_validated` | bool | Target/mechanism confirmed via ChEMBL |
| `drugbank_validated` | bool | Target/mechanism confirmed via DrugBank |
| `discrepancies` | list[string] | Human-readable cross-validation notes |
| `reviewer` | string | Reviewer email or GitHub handle |
| `reviewed_at` | string | ISO 8601 UTC review timestamp |
| `validated` | bool | True only after human sign-off |
| `raw_label_url` | string \| null | URL to source drug label |
| `confidence_score` | float \| null | LLM self-reported confidence [0, 1] |

### Mechanism Class Vocabulary

| Value | Description |
|---|---|
| `inhibitor` | Enzyme or receptor inhibitor |
| `agonist` | Receptor agonist or partial agonist |
| `chaperone` | Pharmacological chaperone / cofactor therapy |
| `ASO` | Antisense oligonucleotide (splice-switching, gene-silencing, or exon-skipping) |
| `siRNA` | Small interfering RNA (GalNAc-conjugated or LNP-formulated) |
| `gene_therapy` | Viral vector gene addition, CRISPR gene editing, or ex-vivo HSC editing |
| `enzyme_replacement` | Recombinant enzyme replacement therapy (ERT) |
| `monoclonal_antibody` | IgG or derived therapeutic antibody |
| `modulator` | CFTR or splicing modulator not fitting ASO/siRNA classes |
| `other` | Catch-all for mechanisms not in the above list |

---

## Per-Row Provenance

Every record in `data/validated/` carries a complete provenance chain:

```
Source API(s): openfda, dailymed
  ↓ cached in data/raw/ (gitignored)
Extraction: Claude claude-sonnet-4-6, prompt v1.2.0
  ↓ written to data/extracted/ (gitignored)
Cross-validation: ChEMBL REST API + DrugBank (if API key available)
  ↓ discrepancies noted in metadata.discrepancies
Human review: reviewer email + ISO 8601 timestamp
  ↓ written to data/validated/ (CHECKED INTO GIT)
```

To reproduce an extraction:
1. `git checkout` the exact commit
2. Note `metadata.prompt_version` and `metadata.extractor_model`
3. The prompt is pinned in `src/fda_strategy_triples/extract/extractor.py`
   under `PROMPT_VERSION = "v1.2.0"`

---

## Known Biases

### Drug-class skew
The seed list of 50 drugs over-represents:
- **RNA therapies** (ASO + siRNA): ~30% of records, reflecting the outsized pace of
  rare-disease oligonucleotide approvals since 2016
- **Alnylam/Ionis/Biogen pipeline drugs**: TTR amyloidosis and SMA each have ≥3 entries
- **Small-molecule enzyme replacement** (MPS disorders): 8 entries

Under-represented:
- Ophthalmology gene therapies (only Luxturna not yet included)
- Oncology-adjacent rare tumours
- Non-US approvals (EMA-only drugs excluded unless also FDA-approved)

### Patient population representation
- Indicated diseases are predominantly Mendelian / single-gene disorders affecting
  patients of European ancestry (e.g. classic PKU, HGPS, CF)
- Some indicated diseases have heavily skewed ethnic prevalence (e.g. sickle cell
  disease is predominantly diagnosed in individuals of African/South Asian ancestry,
  yet the pivotal trial enrollments for voxelotor and lovotibeglogene autotemcel
  were majority non-African)
- Where available, Phase 3 trial demographic breakdowns are noted in
  `primary_citation_pmid` — retrieve from PubMed for full analysis

### Geographic FDA bias
All approval dates are US FDA approvals.  EMA or TGA approvals may predate or
postdate FDA; cross-jurisdiction comparisons require separate curation.

### LLM extraction bias
Claude is used to extract mechanism summaries from label text.  Known failure modes:
- Over-literal transcription of SPL language (may miss mechanistic nuance)
- Inconsistent UniProt assignment for multi-subunit targets
- Gene symbol normalization may fail for non-human gene names

---

## Suggested Uses

1. **Drug-repurposing prior**: filter by `associated_genes` to find all approved
   drugs targeting a gene of interest; `variant_context` narrows to clinically
   validated mutation classes
2. **Agent benchmark**: test LLM agents on gene→drug retrieval; validated records
   provide ground truth for precision/recall evaluation
3. **Education**: the dataset covers mechanism diversity useful for pharmacology
   courses covering rare-disease therapeutics
4. **Regulatory analysis**: `approval_date` + `mechanism_class` enables longitudinal
   analysis of FDA approval trends by modality

---

## Citation

If you use this dataset, please cite:

```bibtex
@dataset{shenoy2025fda_strategy_triples,
  author    = {Shenoy, Amit},
  title     = {{FDA Strategy Triples: A curated dataset of gene–variant–drug–target–mechanism associations for rare diseases}},
  year      = {2025},
  publisher = {GitHub},
  version   = {0.1.0},
  url       = {https://github.com/ashenoy00000/fda-strategy-triples},
  license   = {CC-BY-4.0}
}
```

Primary sources used (not exhaustive):
- OpenFDA: https://api.fda.gov/drug/label.json
- DailyMed: https://dailymed.nlm.nih.gov/dailymed/services/v2/
- ChEMBL: https://www.ebi.ac.uk/chembl/
- DrugBank: https://go.drugbank.com/

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2025-01-15 | Initial release; 10 validated records |
