#!/usr/bin/env python3
"""
Generate frozen release artefacts from data/validated/validated_triples.jsonl.

Writes:
  data/releases/<version>/triples.{jsonl,csv,parquet}
  src/fda_strategy_triples/releases/<version>/triples.{jsonl,csv,parquet}
  datasets/hf_repo/triples.parquet

Run:
    python scripts/generate_release.py
    python scripts/generate_release.py --version v0.1.0
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

VALIDATED = Path("data/validated/validated_triples.jsonl")

PARQUET_SCHEMA = pa.schema([
    ("id",                    pa.string()),
    ("schema_version",        pa.string()),
    ("drug_name_generic",     pa.string()),
    ("drug_name_brand",       pa.string()),
    ("approval_date",         pa.string()),
    ("indicated_disease",     pa.string()),
    ("associated_genes",      pa.list_(pa.string())),
    ("variant_context",       pa.string()),
    ("molecular_target",      pa.string()),
    ("mechanism_class",       pa.string()),
    ("mechanism_summary",     pa.string()),
    ("primary_citation_pmid", pa.string()),
    ("source_apis",           pa.list_(pa.string())),
    ("fetch_timestamp",       pa.string()),
    ("prompt_version",        pa.string()),
    ("extractor_model",       pa.string()),
    ("chembl_validated",      pa.bool_()),
    ("drugbank_validated",    pa.bool_()),
    ("discrepancies",         pa.list_(pa.string())),
    ("reviewer",              pa.string()),
    ("reviewed_at",           pa.string()),
    ("validated",             pa.bool_()),
    ("raw_label_url",         pa.string()),
    ("confidence_score",      pa.float32()),
])


def _to_row(r: dict) -> dict:
    t = r["triple"]
    m = r["metadata"]
    return {
        "id":                    r["id"],
        "schema_version":        r.get("schema_version", "1.0.0"),
        "drug_name_generic":     t["drug_name_generic"],
        "drug_name_brand":       t["drug_name_brand"],
        "approval_date":         t.get("approval_date") or "",
        "indicated_disease":     t["indicated_disease"],
        "associated_genes":      list(t["associated_genes"]),
        "variant_context":       t["variant_context"],
        "molecular_target":      t["molecular_target"],
        "mechanism_class":       t["mechanism_class"],
        "mechanism_summary":     t["mechanism_summary"],
        "primary_citation_pmid": t.get("primary_citation_pmid") or "",
        "source_apis":           list(m["source_apis"]),
        "fetch_timestamp":       m["fetch_timestamp"],
        "prompt_version":        m["prompt_version"],
        "extractor_model":       m["extractor_model"],
        "chembl_validated":      bool(m["chembl_validated"]),
        "drugbank_validated":    bool(m["drugbank_validated"]),
        "discrepancies":         list(m.get("discrepancies", [])),
        "reviewer":              m.get("reviewer") or "",
        "reviewed_at":           m.get("reviewed_at") or "",
        "validated":             bool(m["validated"]),
        "raw_label_url":         r.get("raw_label_url") or "",
        "confidence_score":      float(r.get("confidence_score") or 0.0),
    }


def _flat_for_csv(row: dict) -> dict:
    """Convert list fields to pipe-delimited strings for CSV."""
    out = dict(row)
    for k in ("associated_genes", "source_apis", "discrepancies"):
        out[k] = "|".join(out[k])
    return out


def generate(version: str) -> None:
    records_raw = [
        json.loads(line)
        for line in VALIDATED.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rows = [_to_row(r) for r in records_raw]
    print(f"Loaded {len(rows)} validated records from {VALIDATED}")

    # ── build pyarrow table ────────────────────────────────────────────────
    cols: dict = {field.name: [] for field in PARQUET_SCHEMA}
    for row in rows:
        for field in PARQUET_SCHEMA:
            cols[field.name].append(row[field.name])

    arrays = {
        field.name: pa.array(cols[field.name], type=field.type)
        for field in PARQUET_SCHEMA
    }
    table = pa.table(arrays, schema=PARQUET_SCHEMA)

    # ── destinations ──────────────────────────────────────────────────────
    destinations = [
        Path(f"data/releases/{version}"),
        Path(f"src/fda_strategy_triples/releases/{version}"),
    ]
    hf_dir = Path("datasets/hf_repo")

    for dest in destinations:
        dest.mkdir(parents=True, exist_ok=True)

        # JSONL — verbatim copy of validated file
        jsonl_out = dest / "triples.jsonl"
        shutil.copy2(VALIDATED, jsonl_out)
        print(f"  JSONL -> {jsonl_out}")

        # CSV — flat, pipe-delimited lists
        csv_out = dest / "triples.csv"
        flat_rows = [_flat_for_csv(r) for r in rows]
        with csv_out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(flat_rows[0].keys()))
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"  CSV  -> {csv_out}")

        # Parquet
        parquet_out = dest / "triples.parquet"
        pq.write_table(table, parquet_out, compression="snappy")
        print(f"  Parquet -> {parquet_out} ({parquet_out.stat().st_size:,} bytes)")

    # Copy parquet to HF repo
    hf_dir.mkdir(parents=True, exist_ok=True)
    hf_parquet = hf_dir / "triples.parquet"
    shutil.copy2(destinations[0] / "triples.parquet", hf_parquet)
    print(f"  HF parquet -> {hf_parquet}")

    print(f"\nRelease {version} artefacts generated successfully.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.1.0")
    args = parser.parse_args()
    generate(args.version)


if __name__ == "__main__":
    main()
