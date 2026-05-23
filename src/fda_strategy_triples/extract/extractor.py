"""
Claude-powered structured extraction of FDA drug triples from label text.

Uses the Anthropic tool-use pattern to guarantee schema-conformant JSON output.
Prompt versioning is explicit: bump PROMPT_VERSION when the system prompt changes
so that data/extracted/ records carry an accurate provenance stamp.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
import typer
from rich.console import Console
from rich.progress import track

from fda_strategy_triples.extract.schema import (
    SCHEMA_VERSION,
    DrugSeed,
    ExtractedTriple,
    FDATriple,
    MechanismClass,
    ValidationMetadata,
)
from fda_strategy_triples.fetch import openfda, dailymed

console = Console()
app = typer.Typer(name="fda-extract", help="Extract structured triples from drug labels via Claude.")

PROMPT_VERSION = "v1.2.0"
DEFAULT_MODEL  = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a pharmaceutical data extraction specialist producing structured records \
for a curated dataset of FDA-approved rare-disease drug mechanisms.

Your task is to extract a precise (gene → variant_context → drug → molecular_target → \
mechanism) tuple from the provided drug label text.

Rules:
- Use HGNC official gene symbols (uppercase, no aliases).
- For molecular_target, prefer 'UniProt_accession (SYMBOL)' format when the label or \
  your knowledge confirms it; otherwise use a precise descriptive name.
- variant_context must quote specific variant notation from the label when present \
  (e.g. 'G551D (c.1652G>A, p.Gly551Asp)').
- mechanism_summary must be 1–2 sentences, accurate enough to survive domain-expert audit.
- If the label does not provide information for a field, return null — do NOT fabricate.
- Do NOT include marketing language or efficacy claims in mechanism_summary.
- confidence_score: your honest estimate of extraction accuracy given label quality [0–1].
"""

EXTRACTION_TOOL: dict = {
    "name": "record_fda_triple",
    "description": "Record the extracted FDA drug triple as a structured JSON object.",
    "input_schema": {
        "type": "object",
        "properties": {
            "drug_name_generic": {"type": "string"},
            "drug_name_brand":   {"type": "string"},
            "approval_date":     {"type": ["string", "null"]},
            "indicated_disease": {"type": "string"},
            "associated_genes":  {"type": "array", "items": {"type": "string"}},
            "variant_context":   {"type": "string"},
            "molecular_target":  {"type": "string"},
            "mechanism_summary": {"type": "string"},
            "mechanism_class":   {
                "type": "string",
                "enum": [m.value for m in MechanismClass],
            },
            "primary_citation_pmid": {"type": ["string", "null"]},
            "confidence_score":      {"type": ["number", "null"]},
        },
        "required": [
            "drug_name_generic", "drug_name_brand", "indicated_disease",
            "associated_genes", "variant_context", "molecular_target",
            "mechanism_summary", "mechanism_class",
        ],
    },
}


def _build_user_message(seed: DrugSeed, label_text: str) -> str:
    hints = ""
    if seed.gene_hints:
        hints += f"\nKnown associated genes (hints, verify against label): {', '.join(seed.gene_hints)}"
    if seed.mechanism_hint:
        hints += f"\nExpected mechanism class (hint): {seed.mechanism_hint.value}"
    return (
        f"Extract the FDA triple for: {seed.drug_name_generic} ({seed.drug_name_brand}).\n"
        f"{hints}\n\n"
        f"=== DRUG LABEL TEXT ===\n{label_text[:18000]}"  # stay well under 200k context
    )


def extract_triple(
    seed: DrugSeed,
    label_text: str,
    *,
    model: str = DEFAULT_MODEL,
    source_apis: list[str],
    raw_label_url: Optional[str] = None,
) -> ExtractedTriple:
    """
    Call Claude with the extraction tool and return a validated ExtractedTriple.

    Raises ValueError if the model returns no tool call (should not happen with
    tool_choice='any', but defensive).
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": _build_user_message(seed, label_text)}],
    )

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    if not tool_uses:
        raise ValueError(f"Claude returned no tool_use block for '{seed.drug_name_generic}'")

    raw: dict = tool_uses[0].input
    confidence = float(raw.pop("confidence_score", 0.8) or 0.8)

    triple = FDATriple(**{k: v for k, v in raw.items() if k != "confidence_score"})

    metadata = ValidationMetadata(
        source_apis=source_apis,
        fetch_timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_version=PROMPT_VERSION,
        extractor_model=model,
        validated=False,
    )

    return ExtractedTriple(
        triple=triple,
        metadata=metadata,
        raw_label_url=raw_label_url,
        confidence_score=confidence,
        schema_version=SCHEMA_VERSION,
    )


def run_pipeline(
    seeds_path: Path = Path("data/seeds/drug_seeds.json"),
    output_dir: Path = Path("data/extracted"),
    model: str = DEFAULT_MODEL,
    *,
    use_cache: bool = True,
    limit: Optional[int] = None,
) -> list[ExtractedTriple]:
    """
    Run the full extraction pipeline for all seeds.

    Fetches from OpenFDA → DailyMed, extracts with Claude, writes JSONL.
    """
    seeds_data = json.loads(seeds_path.read_text(encoding="utf-8"))
    seeds = [DrugSeed(**s) for s in seeds_data]
    if limit:
        seeds = seeds[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "extracted_triples.jsonl"

    results: list[ExtractedTriple] = []

    for seed in track(seeds, description="Extracting triples…"):
        if seed.needs_manual_verification:
            console.print(f"[yellow]Skipping '{seed.drug_name_generic}' (needs_manual_verification)[/yellow]")
            continue

        # 1. Fetch from OpenFDA
        label = openfda.fetch_label_by_name(seed.drug_name_generic, use_cache=use_cache)
        source_apis = []
        label_text = ""
        raw_url = None

        if label:
            source_apis.append("openfda")
            label_text = openfda.extract_label_text(label)

        # 2. Augment with DailyMed
        dm_label = None
        if seed.dailymed_set_id:
            dm_label = dailymed.fetch_spls_by_setid(seed.dailymed_set_id, use_cache=use_cache)
        else:
            dm_label = dailymed.fetch_label_by_name(seed.drug_name_generic, use_cache=use_cache)

        if dm_label:
            source_apis.append("dailymed")
            sections = dailymed.extract_sections(dm_label)
            dm_text = "\n\n".join(
                f"[DailyMed {k}]\n{v}" for k, v in sections.items() if v
            )
            label_text = (label_text + "\n\n" + dm_text).strip()
            set_id = (
                seed.dailymed_set_id
                or dm_label.get("data", {}).get("setid", "")
            )
            if set_id:
                raw_url = dailymed.label_url(set_id)

        if not label_text:
            console.print(f"[red]No label text for '{seed.drug_name_generic}'; skipping[/red]")
            continue

        try:
            record = extract_triple(
                seed,
                label_text,
                model=model,
                source_apis=source_apis,
                raw_label_url=raw_url,
            )
            results.append(record)
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
            console.print(f"[green]✓[/green] {seed.drug_name_generic}")
        except Exception as exc:
            console.print(f"[red]✗ {seed.drug_name_generic}: {exc}[/red]")

    return results


@app.command()
def run(
    seeds: Path = typer.Option(Path("data/seeds/drug_seeds.json"), help="Path to seeds JSON"),
    output: Path = typer.Option(Path("data/extracted"), help="Output directory"),
    model: str = typer.Option(DEFAULT_MODEL, help="Claude model ID"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Process only first N seeds"),
) -> None:
    """Run the full ETL extraction pipeline."""
    records = run_pipeline(seeds, output, model, use_cache=not no_cache, limit=limit)
    console.print(f"\n[bold green]Done.[/bold green] Extracted {len(records)} triples → {output}")
