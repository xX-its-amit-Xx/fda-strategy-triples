"""
Fetch Structured Product Labels (SPLs) from DailyMed v2 REST API.

Docs: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
No authentication required; be polite (≤60 req/min).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()

BASE_URL   = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
_CACHE_DIR = Path("data/raw/dailymed")
_MIN_INTERVAL = 1.1  # ~55 req/min


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
def _get(url: str, params: Optional[dict] = None) -> dict:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params=params or {}, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


def search_drug(drug_name: str) -> list[dict]:
    """Search DailyMed for SPL records matching *drug_name*. Returns metadata list."""
    time.sleep(_MIN_INTERVAL)
    data = _get(f"{BASE_URL}/drugnames.json", {"drug_name": drug_name, "pagesize": 5})
    return data.get("data", [])


def fetch_spls_by_setid(set_id: str, *, use_cache: bool = True) -> Optional[dict]:
    """Retrieve the full SPL JSON for a known DailyMed *set_id*."""
    cache_path = _CACHE_DIR / f"{set_id}.json"
    if use_cache and cache_path.exists():
        console.print(f"[dim]cache hit:[/dim] {cache_path}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    try:
        data = _get(f"{BASE_URL}/spls/{set_id}.json")
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]DailyMed error {exc.response.status_code} for set_id={set_id}[/red]")
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def fetch_label_by_name(drug_name: str, *, use_cache: bool = True) -> Optional[dict]:
    """
    High-level: search DailyMed by name, pick the most recent human-prescription
    label, and return the full SPL JSON.
    """
    slug = drug_name.lower().replace(" ", "_").replace("/", "-")
    name_cache = _CACHE_DIR / f"{slug}_search.json"

    if use_cache and name_cache.exists():
        hits = json.loads(name_cache.read_text(encoding="utf-8"))
    else:
        hits = search_drug(drug_name)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        name_cache.write_text(json.dumps(hits, indent=2), encoding="utf-8")

    if not hits:
        console.print(f"[yellow]DailyMed: no results for '{drug_name}'[/yellow]")
        return None

    set_id = hits[0].get("setid") or hits[0].get("set_id")
    if not set_id:
        return None

    return fetch_spls_by_setid(set_id, use_cache=use_cache)


def extract_sections(spl: dict) -> dict[str, str]:
    """
    Pull the key narrative sections from a DailyMed SPL response.

    Returns a dict of {section_code: text} for the sections most
    relevant to mechanism extraction.
    """
    sections_of_interest = {
        "34067-9":  "indications_usage",
        "34089-3":  "description",
        "43685-7":  "warnings_precautions",
        "34090-1":  "clinical_pharmacology",
        "43679-0":  "mechanism_of_action",
        "34092-7":  "clinical_studies",
        "34068-7":  "dosage_administration",
    }
    result: dict[str, str] = {}
    for section in spl.get("data", {}).get("sections", []):
        code = section.get("code", "")
        if code in sections_of_interest:
            key = sections_of_interest[code]
            result[key] = section.get("text", "")
    return result


def label_url(set_id: str) -> str:
    return f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
