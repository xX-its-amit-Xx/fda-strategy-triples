"""
Interactive human review CLI for fda-strategy-triples.

Usage:
    fda-review start --input data/extracted/extracted_triples.jsonl
    fda-review status
    fda-review export

Each record is shown to the reviewer in a rich panel.  The reviewer can:
  [a] Accept   — marks validated=True
  [e] Edit     — opens $EDITOR to hand-edit the JSON, then re-validates
  [r] Reject   — excludes from validated set with a reason note
  [s] Skip     — defer to next session (record stays unreviewed)
  [q] Quit     — save progress and exit

Accepted records are appended to data/validated/validated_triples.jsonl.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from fda_strategy_triples.extract.schema import ExtractedTriple, ValidationMetadata

app = typer.Typer(name="fda-review", help="Interactive human review of extracted triples.")
console = Console()

_DEFAULT_INPUT     = Path("data/extracted/extracted_triples.jsonl")
_DEFAULT_VALIDATED = Path("data/validated/validated_triples.jsonl")
_REVIEW_STATE      = Path("data/extracted/.review_state.json")


def _load_state() -> dict:
    if _REVIEW_STATE.exists():
        return json.loads(_REVIEW_STATE.read_text(encoding="utf-8"))
    return {"reviewed_ids": [], "rejected_ids": []}


def _save_state(state: dict) -> None:
    _REVIEW_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _render_record(record: ExtractedTriple, idx: int, total: int) -> None:
    t = record.triple
    md = record.metadata

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", width=24)
    table.add_column("Value", style="white")

    table.add_row("Generic name",      t.drug_name_generic)
    table.add_row("Brand name",        t.drug_name_brand)
    table.add_row("Approval date",     t.approval_date or "—")
    table.add_row("Indicated disease", t.indicated_disease)
    table.add_row("Associated genes",  ", ".join(t.associated_genes))
    table.add_row("Variant context",   t.variant_context)
    table.add_row("Molecular target",  t.molecular_target)
    table.add_row("Mechanism class",   t.mechanism_class.value)
    table.add_row("Mechanism summary", t.mechanism_summary)
    table.add_row("Primary PMID",      t.primary_citation_pmid or "—")
    table.add_row("Source APIs",       ", ".join(md.source_apis))
    table.add_row("ChEMBL validated",  "✓" if md.chembl_validated else "✗")
    table.add_row("DrugBank validated","✓" if md.drugbank_validated else "✗")
    table.add_row("Confidence",        f"{record.confidence_score:.2f}" if record.confidence_score else "—")
    if md.discrepancies:
        table.add_row("Discrepancies",
                      "\n".join(f"• {d}" for d in md.discrepancies),
                      )

    console.print(
        Panel(
            table,
            title=f"[bold]Record {idx}/{total} — ID: {record.id[:12]}…[/bold]",
            border_style="blue",
        )
    )


def _open_editor(record: ExtractedTriple) -> Optional[ExtractedTriple]:
    """Open record JSON in $EDITOR for manual correction. Returns edited record or None."""
    editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(record.model_dump_json(indent=2))
        tmp_path = tmp.name

    subprocess.run([editor, tmp_path], check=True)  # noqa: S603

    try:
        edited = ExtractedTriple.model_validate_json(
            Path(tmp_path).read_text(encoding="utf-8")
        )
    except Exception as exc:
        console.print(f"[red]Validation error in edited JSON: {exc}[/red]")
        return None
    finally:
        os.unlink(tmp_path)

    return edited


@app.command()
def start(
    input_file: Path = typer.Option(_DEFAULT_INPUT, "--input", "-i"),
    output_file: Path = typer.Option(_DEFAULT_VALIDATED, "--output", "-o"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer", "-r",
                                           help="Your email or GitHub handle (stored in metadata)"),
    skip_validated: bool = typer.Option(True, help="Skip records already in output_file"),
) -> None:
    """Start an interactive review session."""
    if not reviewer:
        reviewer = Prompt.ask("Your reviewer ID (email or GitHub handle)")

    records = [
        ExtractedTriple.model_validate_json(line)
        for line in input_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    state = _load_state()
    already_reviewed = set(state["reviewed_ids"] + state["rejected_ids"])

    existing_validated_ids: set[str] = set()
    if skip_validated and output_file.exists():
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_validated_ids.add(
                    ExtractedTriple.model_validate_json(line).id
                )

    pending = [
        r for r in records
        if r.id not in already_reviewed and r.id not in existing_validated_ids
    ]
    total = len(pending)
    if total == 0:
        console.print("[green]All records reviewed. Nothing to do.[/green]")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)

    for idx, record in enumerate(pending, 1):
        _render_record(record, idx, total)
        console.print(
            "\n[bold]Action:[/bold] "
            "[a] Accept  [e] Edit  [r] Reject  [s] Skip  [q] Quit\n"
        )

        while True:
            choice = Prompt.ask("Choice", choices=["a", "e", "r", "s", "q"], default="s")

            if choice == "q":
                _save_state(state)
                console.print("[yellow]Session saved. Run 'fda-review start' to continue.[/yellow]")
                return

            elif choice == "s":
                console.print("[dim]Skipped.[/dim]")
                break

            elif choice == "r":
                reason = Prompt.ask("Rejection reason")
                state["rejected_ids"].append(record.id)
                console.print(f"[red]Rejected: {reason}[/red]")
                _save_state(state)
                break

            elif choice == "e":
                edited = _open_editor(record)
                if edited is None:
                    console.print("[yellow]Edit cancelled; re-displaying record.[/yellow]")
                    _render_record(record, idx, total)
                    continue
                record = edited
                _render_record(record, idx, total)
                continue

            elif choice == "a":
                now = datetime.now(timezone.utc).isoformat()
                validated_meta = record.metadata.model_copy(
                    update={
                        "validated":   True,
                        "reviewer":    reviewer,
                        "reviewed_at": now,
                    }
                )
                validated_record = record.model_copy(update={"metadata": validated_meta})
                with output_file.open("a", encoding="utf-8") as fh:
                    fh.write(validated_record.model_dump_json() + "\n")
                state["reviewed_ids"].append(record.id)
                _save_state(state)
                console.print("[green]✓ Accepted and written to validated set.[/green]")
                break

        console.rule()

    _save_state(state)
    console.print(f"\n[bold green]Review session complete.[/bold green] "
                  f"Validated records in {output_file}.")


@app.command()
def status(
    input_file: Path = typer.Option(_DEFAULT_INPUT),
    output_file: Path = typer.Option(_DEFAULT_VALIDATED),
) -> None:
    """Show review progress statistics."""
    total = sum(
        1 for line in input_file.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    validated = 0
    if output_file.exists():
        validated = sum(
            1 for line in output_file.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    state = _load_state()
    rejected = len(state["rejected_ids"])

    table = Table(title="Review Status", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="bold white", justify="right")
    table.add_row("Total extracted",  str(total))
    table.add_row("Validated",        str(validated))
    table.add_row("Rejected",         str(rejected))
    table.add_row("Remaining",        str(total - validated - rejected))
    console.print(table)


@app.command()
def export(
    output_file: Path = typer.Option(_DEFAULT_VALIDATED),
    csv_out: Optional[Path] = typer.Option(None, "--csv"),
) -> None:
    """Print a summary of validated records, optionally export to CSV."""
    if not output_file.exists():
        console.print("[red]No validated file found.[/red]")
        raise typer.Exit(1)

    records = [
        ExtractedTriple.model_validate_json(line)
        for line in output_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    console.print(f"[green]{len(records)} validated records in {output_file}[/green]")

    if csv_out:
        import csv
        with csv_out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "id", "drug_name_generic", "drug_name_brand", "approval_date",
                "indicated_disease", "associated_genes", "variant_context",
                "molecular_target", "mechanism_class", "mechanism_summary",
                "primary_citation_pmid", "reviewer", "reviewed_at",
            ])
            writer.writeheader()
            for r in records:
                writer.writerow({
                    "id":                    r.id,
                    "drug_name_generic":     r.triple.drug_name_generic,
                    "drug_name_brand":       r.triple.drug_name_brand,
                    "approval_date":         r.triple.approval_date or "",
                    "indicated_disease":     r.triple.indicated_disease,
                    "associated_genes":      "|".join(r.triple.associated_genes),
                    "variant_context":       r.triple.variant_context,
                    "molecular_target":      r.triple.molecular_target,
                    "mechanism_class":       r.triple.mechanism_class.value,
                    "mechanism_summary":     r.triple.mechanism_summary,
                    "primary_citation_pmid": r.triple.primary_citation_pmid or "",
                    "reviewer":              r.metadata.reviewer or "",
                    "reviewed_at":           r.metadata.reviewed_at or "",
                })
        console.print(f"[green]CSV written to {csv_out}[/green]")
