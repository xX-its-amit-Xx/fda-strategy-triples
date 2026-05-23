"""
Export validated triples to JSON Lines and CSV.

JSONL format: one ExtractedTriple JSON object per line (minified).
CSV format: flat, with pipe-delimited list fields.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from fda_strategy_triples.extract.schema import ExtractedTriple

app = typer.Typer(name="fda-export-jsonl", help="Export validated triples to JSONL and CSV.")
console = Console()

_DEFAULT_VALIDATED = Path("data/validated/validated_triples.jsonl")


def load_validated(path: Path) -> list[ExtractedTriple]:
    return [
        ExtractedTriple.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def to_flat_dict(record: ExtractedTriple) -> dict:
    """Flatten an ExtractedTriple into a single-level dict suitable for CSV."""
    t = record.triple
    m = record.metadata
    return {
        "id":                    record.id,
        "schema_version":        record.schema_version,
        "drug_name_generic":     t.drug_name_generic,
        "drug_name_brand":       t.drug_name_brand,
        "approval_date":         t.approval_date or "",
        "indicated_disease":     t.indicated_disease,
        "associated_genes":      "|".join(t.associated_genes),
        "variant_context":       t.variant_context,
        "molecular_target":      t.molecular_target,
        "mechanism_class":       t.mechanism_class.value,
        "mechanism_summary":     t.mechanism_summary,
        "primary_citation_pmid": t.primary_citation_pmid or "",
        "source_apis":           "|".join(m.source_apis),
        "fetch_timestamp":       m.fetch_timestamp,
        "prompt_version":        m.prompt_version,
        "extractor_model":       m.extractor_model,
        "chembl_validated":      str(m.chembl_validated),
        "drugbank_validated":    str(m.drugbank_validated),
        "discrepancies":         " | ".join(m.discrepancies),
        "reviewer":              m.reviewer or "",
        "reviewed_at":           m.reviewed_at or "",
        "validated":             str(m.validated),
        "raw_label_url":         record.raw_label_url or "",
        "confidence_score":      str(record.confidence_score) if record.confidence_score is not None else "",
    }


CSV_FIELDS = list(to_flat_dict(  # derive fieldnames from schema
    ExtractedTriple.model_construct(
        triple=None,  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
    )
).__class__.__dict__  # placeholder — fields defined above
)


def export_jsonl(records: list[ExtractedTriple], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(r.model_dump_json() + "\n")
    console.print(f"[green]JSONL → {output} ({len(records)} records)[/green]")


def export_csv(records: list[ExtractedTriple], output: Path) -> None:
    rows = [to_flat_dict(r) for r in records]
    if not rows:
        console.print("[yellow]No records to export.[/yellow]")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"[green]CSV → {output} ({len(records)} records)[/green]")


@app.command()
def run(
    input_file: Path = typer.Option(_DEFAULT_VALIDATED, "--input", "-i"),
    out_jsonl: Optional[Path] = typer.Option(None, "--jsonl"),
    out_csv:   Optional[Path] = typer.Option(None, "--csv"),
) -> None:
    """Export validated triples to JSONL and/or CSV."""
    records = load_validated(input_file)
    if out_jsonl:
        export_jsonl(records, out_jsonl)
    if out_csv:
        export_csv(records, out_csv)
    if not out_jsonl and not out_csv:
        console.print(f"[cyan]{len(records)} validated records loaded.[/cyan]  "
                      "Pass --jsonl and/or --csv to export.")
