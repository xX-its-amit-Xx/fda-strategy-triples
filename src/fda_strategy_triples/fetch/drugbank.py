"""
Fetch drug records from the DrugBank REST API for cross-validation.

IMPORTANT: DrugBank requires a commercial or academic license.
Set the DRUGBANK_API_KEY environment variable before using this module.
Without a key, all calls will return None and log a warning.

License info: https://go.drugbank.com/releases/latest#open-data
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()

BASE_URL   = "https://api.drugbank.com/v1"
_CACHE_DIR = Path("data/raw/drugbank")
_MIN_INTERVAL = 0.5


def _api_key() -> str:
    key = os.environ.get("DRUGBANK_API_KEY", "")
    if not key:
        console.print(
            "[yellow]DRUGBANK_API_KEY not set; DrugBank validation will be skipped.[/yellow]"
        )
    return key


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def _get(url: str, api_key: str, params: Optional[dict] = None) -> dict:
    headers = {"Authorization": api_key, "Accept": "application/json"}
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params=params or {}, headers=headers)
        r.raise_for_status()
        return r.json()


def fetch_by_drugbank_id(db_id: str, *, use_cache: bool = True) -> Optional[dict]:
    """
    Retrieve a DrugBank record by accession (e.g. 'DB11945').

    Returns None if the API key is missing or the record is not found.
    """
    key = _api_key()
    if not key:
        return None

    cache_path = _CACHE_DIR / f"{db_id}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(_MIN_INTERVAL)
    try:
        data = _get(f"{BASE_URL}/drugs/{db_id}", key)
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]DrugBank error {exc.response.status_code} for {db_id}[/red]")
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def extract_validation_fields(db_id: str) -> dict:
    """
    Pull fields relevant for cross-validation: targets, categories, mechanism.
    Returns an empty dict if unavailable.
    """
    record = fetch_by_drugbank_id(db_id)
    if record is None:
        return {}

    targets = record.get("targets", [])
    return {
        "drugbank_id": db_id,
        "name": record.get("name"),
        "drug_type": record.get("drug_type"),
        "categories": [c.get("category") for c in record.get("categories", [])],
        "mechanism_of_action": record.get("mechanism_of_action", ""),
        "targets": [
            {
                "name": t.get("name"),
                "uniprot_id": next(
                    (
                        xr.get("identifier")
                        for xr in t.get("polypeptide", {}).get("external_identifiers", [])
                        if xr.get("resource") == "UniProtKB"
                    ),
                    None,
                ),
                "actions": t.get("actions", []),
            }
            for t in targets[:5]
        ],
    }
