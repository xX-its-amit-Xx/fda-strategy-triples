"""
Export validated triples to a Hugging Face Datasets-compatible Parquet file.

Produces a DatasetDict with a single 'train' split (all validated records),
plus a DatasetInfo card compatible with datasets.load_dataset().

Usage:
    python -m fda_strategy_triples.export.to_hf_dataset
    # or via CLI entry point defined in pyproject.toml (fda-export)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from fda_strategy_triples.export.to_jsonl import load_validated, to_flat_dict

console = Console()
app = typer.Typer(name="fda-export-hf", help="Export validated triples to HF Datasets parquet.")

_DEFAULT_VALIDATED = Path("data/validated/validated_triples.jsonl")
_DEFAULT_OUTPUT    = Path("data/validated/hf_dataset")


def build_features() -> "datasets.Features":
    """Define the HF Datasets Features schema (lazy import for optional dep)."""
    from datasets import ClassLabel, Features, Sequence, Value

    return Features({
        "id":                    Value("string"),
        "schema_version":        Value("string"),
        "drug_name_generic":     Value("string"),
        "drug_name_brand":       Value("string"),
        "approval_date":         Value("string"),
        "indicated_disease":     Value("string"),
        "associated_genes":      Sequence(Value("string")),
        "variant_context":       Value("string"),
        "molecular_target":      Value("string"),
        "mechanism_class":       ClassLabel(names=[
            "inhibitor", "agonist", "chaperone", "ASO", "siRNA",
            "gene_therapy", "enzyme_replacement", "monoclonal_antibody",
            "modulator", "other",
        ]),
        "mechanism_summary":     Value("string"),
        "primary_citation_pmid": Value("string"),
        "source_apis":           Sequence(Value("string")),
        "fetch_timestamp":       Value("string"),
        "prompt_version":        Value("string"),
        "extractor_model":       Value("string"),
        "chembl_validated":      Value("bool"),
        "drugbank_validated":    Value("bool"),
        "discrepancies":         Sequence(Value("string")),
        "reviewer":              Value("string"),
        "reviewed_at":           Value("string"),
        "validated":             Value("bool"),
        "raw_label_url":         Value("string"),
        "confidence_score":      Value("float32"),
    })


def _record_to_hf_row(record) -> dict:
    """Convert an ExtractedTriple to an HF-compatible flat row with proper types."""
    t = record.triple
    m = record.metadata
    return {
        "id":                    record.id,
        "schema_version":        record.schema_version,
        "drug_name_generic":     t.drug_name_generic,
        "drug_name_brand":       t.drug_name_brand,
        "approval_date":         t.approval_date or "",
        "indicated_disease":     t.indicated_disease,
        "associated_genes":      list(t.associated_genes),
        "variant_context":       t.variant_context,
        "molecular_target":      t.molecular_target,
        "mechanism_class":       t.mechanism_class.value,
        "mechanism_summary":     t.mechanism_summary,
        "primary_citation_pmid": t.primary_citation_pmid or "",
        "source_apis":           list(m.source_apis),
        "fetch_timestamp":       m.fetch_timestamp,
        "prompt_version":        m.prompt_version,
        "extractor_model":       m.extractor_model,
        "chembl_validated":      m.chembl_validated,
        "drugbank_validated":    m.drugbank_validated,
        "discrepancies":         list(m.discrepancies),
        "reviewer":              m.reviewer or "",
        "reviewed_at":           m.reviewed_at or "",
        "validated":             m.validated,
        "raw_label_url":         record.raw_label_url or "",
        "confidence_score":      float(record.confidence_score) if record.confidence_score is not None else 0.0,
    }


def export_hf(
    records_path: Path = _DEFAULT_VALIDATED,
    output_dir: Path = _DEFAULT_OUTPUT,
) -> None:
    """Build a DatasetDict and save to Parquet + dataset_info.json."""
    try:
        from datasets import Dataset, DatasetDict, DatasetInfo
    except ImportError:
        console.print("[red]`datasets` not installed. Run: pip install datasets[/red]")
        raise

    records = load_validated(records_path)
    rows = [_record_to_hf_row(r) for r in records]

    if not rows:
        console.print("[yellow]No validated records to export.[/yellow]")
        return

    features = build_features()
    ds = Dataset.from_list(rows, features=features)
    dsd = DatasetDict({"train": ds})

    output_dir.mkdir(parents=True, exist_ok=True)
    dsd.save_to_disk(str(output_dir))

    console.print(
        f"[green]HF Dataset → {output_dir}  ({len(rows)} rows, "
        f"features: {list(features.keys()[:5])}… )[/green]"
    )


@app.command()
def run(
    input_file: Path = typer.Option(_DEFAULT_VALIDATED, "--input", "-i"),
    output_dir: Path = typer.Option(_DEFAULT_OUTPUT, "--output", "-o"),
) -> None:
    """Build and save a Hugging Face Dataset from validated triples."""
    export_hf(input_file, output_dir)
