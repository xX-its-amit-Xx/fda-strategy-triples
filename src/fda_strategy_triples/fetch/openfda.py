"""
Fetch drug labels from the OpenFDA drug/label endpoint.

Rate limits (unauthenticated): 240 req/min, 1,000 req/day.
Set OPENFDA_API_KEY env var to lift the day cap.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()
app = typer.Typer(name="fda-fetch", help="Fetch OpenFDA structured product labels.")

BASE_URL = "https://api.fda.gov/drug/label.json"
_CACHE_DIR = Path("data/raw/openfda")
_MIN_INTERVAL = 0.26  # ~230 req/min to stay safely under limit


def _api_key() -> dict[str, str]:
    key = os.environ.get("OPENFDA_API_KEY", "")
    return {"api_key": key} if key else {}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
def _get(params: dict) -> dict:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(BASE_URL, params={**params, **_api_key()})
        r.raise_for_status()
        return r.json()


def fetch_label_by_name(drug_name: str, *, use_cache: bool = True) -> Optional[dict]:
    """Return the first matching SPL label JSON for *drug_name*, or None."""
    slug = drug_name.lower().replace(" ", "_").replace("/", "-")
    cache_path = _CACHE_DIR / f"{slug}.json"

    if use_cache and cache_path.exists():
        console.print(f"[dim]cache hit:[/dim] {cache_path}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1,
    }
    try:
        data = _get(params)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            console.print(f"[yellow]OpenFDA 404 for '{drug_name}'; trying brand name search[/yellow]")
            params["search"] = f'openfda.brand_name:"{drug_name}"'
            try:
                data = _get(params)
            except httpx.HTTPStatusError:
                console.print(f"[red]No OpenFDA record found for '{drug_name}'[/red]")
                return None
        else:
            raise

    results = data.get("results", [])
    if not results:
        return None

    label = results[0]
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(label, indent=2), encoding="utf-8")
    return label


def extract_label_text(label: dict) -> str:
    """Concatenate the most informative SPL sections into a single text blob."""
    sections = [
        "description",
        "indications_and_usage",
        "mechanism_of_action",
        "clinical_pharmacology",
        "warnings_and_cautions",
        "dosage_and_administration",
        "clinical_studies",
    ]
    parts: list[str] = []
    for section in sections:
        content = label.get(section)
        if content:
            text = content[0] if isinstance(content, list) else content
            parts.append(f"## {section.upper()}\n{text}")
    return "\n\n".join(parts)


def get_openfda_metadata(label: dict) -> dict:
    """Return a cleaned metadata dict from the openfda sub-object."""
    openfda = label.get("openfda", {})
    return {
        "application_number": openfda.get("application_number", []),
        "brand_name": openfda.get("brand_name", []),
        "generic_name": openfda.get("generic_name", []),
        "manufacturer_name": openfda.get("manufacturer_name", []),
        "route": openfda.get("route", []),
        "substance_name": openfda.get("substance_name", []),
        "nui": openfda.get("nui", []),
        "pharm_class_moa": openfda.get("pharm_class_moa", []),
        "pharm_class_epc": openfda.get("pharm_class_epc", []),
    }


@app.command()
def fetch(
    drug_name: str = typer.Argument(..., help="Generic or brand name to fetch"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass local cache"),
) -> None:
    """Fetch and cache an OpenFDA label for DRUG_NAME."""
    label = fetch_label_by_name(drug_name, use_cache=not no_cache)
    if label:
        console.print_json(json.dumps(get_openfda_metadata(label)))
    else:
        console.print(f"[red]No label found for '{drug_name}'[/red]")
        raise typer.Exit(1)
