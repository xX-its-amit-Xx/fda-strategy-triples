#!/usr/bin/env python3
"""
End-to-end pipeline runner for fda-strategy-triples.

Steps:
  1. Fetch labels from OpenFDA + DailyMed for each seed
  2. Extract structured triple via Claude
  3. Cross-validate against ChEMBL (DrugBank optional)
  4. Write to data/extracted/extracted_triples.jsonl

Run:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --limit 5 --no-cache
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from fda_strategy_triples.extract.extractor import run_pipeline
from fda_strategy_triples.validate.cross_check import cross_check_file

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="FDA Strategy Triples ETL Pipeline")
    parser.add_argument("--seeds", default="data/seeds/drug_seeds.json")
    parser.add_argument("--extracted-dir", default="data/extracted")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N seeds")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--skip-cross-check", action="store_true")
    args = parser.parse_args()

    seeds_path    = Path(args.seeds)
    extracted_dir = Path(args.extracted_dir)

    console.rule("[bold blue]Step 1–2: Fetch + Extract[/bold blue]")
    run_pipeline(
        seeds_path=seeds_path,
        output_dir=extracted_dir,
        model=args.model,
        use_cache=not args.no_cache,
        limit=args.limit,
    )

    if not args.skip_cross_check:
        console.rule("[bold blue]Step 3: Cross-Validate[/bold blue]")
        extracted_path = extracted_dir / "extracted_triples.jsonl"
        crosschecked_path = extracted_dir / "crosschecked_triples.jsonl"
        if extracted_path.exists():
            cross_check_file(extracted_path, seeds_path, crosschecked_path)
        else:
            console.print("[yellow]No extracted file found; skipping cross-check.[/yellow]")

    console.rule()
    console.print(
        "[bold green]Pipeline complete.[/bold green]\n"
        "Next step: run [cyan]fda-review start[/cyan] to validate records."
    )


if __name__ == "__main__":
    main()
