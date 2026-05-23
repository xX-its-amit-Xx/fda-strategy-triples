"""
Fetch drug records from ChEMBL REST API for cross-validation.

Docs: https://www.ebi.ac.uk/chembl/api/data/
No authentication required.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()

BASE_URL   = "https://www.ebi.ac.uk/chembl/api/data"
_CACHE_DIR = Path("data/raw/chembl")
_MIN_INTERVAL = 0.5


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
def _get(url: str, params: Optional[dict] = None) -> dict:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params={**(params or {}), "format": "json"})
        r.raise_for_status()
        return r.json()


def fetch_by_chembl_id(chembl_id: str, *, use_cache: bool = True) -> Optional[dict]:
    """Retrieve the ChEMBL molecule record for *chembl_id* (e.g. 'CHEMBL1950026')."""
    cache_path = _CACHE_DIR / f"{chembl_id}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    try:
        data = _get(f"{BASE_URL}/molecule/{chembl_id}.json")
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]ChEMBL error {exc.response.status_code} for {chembl_id}[/red]")
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def search_by_name(name: str, *, use_cache: bool = True) -> list[dict]:
    """Search ChEMBL molecules by preferred name; returns top 5 hits."""
    slug = name.lower().replace(" ", "_").replace("/", "-")
    cache_path = _CACHE_DIR / f"search_{slug}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    data = _get(
        f"{BASE_URL}/molecule.json",
        {"pref_name__iexact": name, "limit": 5},
    )
    hits = data.get("molecules", [])
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    return hits


def fetch_mechanism(chembl_id: str, *, use_cache: bool = True) -> list[dict]:
    """Return mechanism-of-action records for *chembl_id*."""
    cache_path = _CACHE_DIR / f"{chembl_id}_moa.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    data = _get(f"{BASE_URL}/mechanism.json", {"molecule_chembl_id": chembl_id})
    mechanisms = data.get("mechanisms", [])
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(mechanisms, indent=2), encoding="utf-8")
    return mechanisms


def extract_validation_fields(chembl_id: str) -> dict:
    """
    Pull the fields needed for cross-validation: target, action type, max phase.
    Returns an empty dict if the ChEMBL ID is not found.
    """
    mol = fetch_by_chembl_id(chembl_id)
    if mol is None:
        return {}
    mechanisms = fetch_mechanism(chembl_id)
    return {
        "chembl_id": chembl_id,
        "max_phase": mol.get("max_phase"),
        "molecule_type": mol.get("molecule_type"),
        "pref_name": mol.get("pref_name"),
        "mechanisms": [
            {
                "action_type": m.get("action_type"),
                "target_chembl_id": m.get("target_chembl_id"),
                "target_name": m.get("target_name"),
                "mechanism_of_action": m.get("mechanism_of_action"),
            }
            for m in mechanisms
        ],
    }
