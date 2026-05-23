"""
Cross-validate extracted triples against ChEMBL and DrugBank.

Checks:
  1. Mechanism class agreement
  2. Target name / UniProt accession agreement
  3. Max phase consistency (warn if ChEMBL max_phase < 4 for approved drugs)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from fda_strategy_triples.extract.schema import ExtractedTriple, MechanismClass
from fda_strategy_triples.fetch import chembl as chembl_fetch
from fda_strategy_triples.fetch import drugbank as drugbank_fetch

console = Console()

# Rough mapping from ChEMBL action_type to our MechanismClass
_CHEMBL_ACTION_MAP: dict[str, MechanismClass] = {
    "INHIBITOR":             MechanismClass.inhibitor,
    "AGONIST":               MechanismClass.agonist,
    "ANTAGONIST":            MechanismClass.inhibitor,
    "POSITIVE ALLOSTERIC MODULATOR": MechanismClass.chaperone,
    "MODULATOR":             MechanismClass.modulator,
}


def _chembl_mechanism_class(mechanisms: list[dict]) -> Optional[MechanismClass]:
    for m in mechanisms:
        action = (m.get("action_type") or "").upper()
        if action in _CHEMBL_ACTION_MAP:
            return _CHEMBL_ACTION_MAP[action]
    return None


def cross_check_record(
    record: ExtractedTriple,
    chembl_id: Optional[str] = None,
    drugbank_id: Optional[str] = None,
) -> tuple[ExtractedTriple, list[str]]:
    """
    Cross-check one record against ChEMBL and DrugBank.

    Returns the updated record (with validation flags set) and a list of
    discrepancy strings.  The original record is not mutated; a copy is returned.
    """
    discrepancies: list[str] = list(record.metadata.discrepancies)
    chembl_ok = False
    drugbank_ok = False

    # ── ChEMBL ────────────────────────────────────────────────────────────────
    if chembl_id:
        chembl_data = chembl_fetch.extract_validation_fields(chembl_id)
        if chembl_data:
            # Max-phase check
            max_phase = chembl_data.get("max_phase")
            if max_phase is not None and max_phase < 4 and not record.triple.approval_date == "investigational":
                discrepancies.append(
                    f"ChEMBL max_phase={max_phase} but drug has an FDA approval date "
                    f"— ChEMBL record may be incomplete or refer to a different indication."
                )

            # Mechanism class check (lenient: only flag if clearly contradicted)
            chembl_class = _chembl_mechanism_class(chembl_data.get("mechanisms", []))
            if chembl_class and chembl_class != record.triple.mechanism_class:
                # Gene/RNA therapies and ERTs don't have ChEMBL mechanism records
                if record.triple.mechanism_class not in (
                    MechanismClass.gene_therapy, MechanismClass.enzyme_replacement,
                    MechanismClass.aso, MechanismClass.sirna,
                ):
                    discrepancies.append(
                        f"Mechanism class mismatch: extracted={record.triple.mechanism_class.value}, "
                        f"ChEMBL inferred={chembl_class.value}"
                    )

            chembl_ok = True

    # ── DrugBank ──────────────────────────────────────────────────────────────
    if drugbank_id:
        db_data = drugbank_fetch.extract_validation_fields(drugbank_id)
        if db_data:
            # Check UniProt IDs in targets against molecular_target field
            uniprot_ids = [
                t["uniprot_id"]
                for t in db_data.get("targets", [])
                if t.get("uniprot_id")
            ]
            extracted_target = record.triple.molecular_target
            if uniprot_ids and not any(uid in extracted_target for uid in uniprot_ids):
                discrepancies.append(
                    f"DrugBank primary target UniProt IDs {uniprot_ids} not found in "
                    f"extracted molecular_target='{extracted_target}' — verify manually."
                )
            drugbank_ok = True

    updated = record.model_copy(deep=True)
    updated.metadata = record.metadata.model_copy(
        update={
            "chembl_validated": chembl_ok,
            "drugbank_validated": drugbank_ok,
            "discrepancies": discrepancies,
        }
    )
    return updated, discrepancies


def cross_check_file(
    extracted_path: Path,
    seeds_path: Path,
    output_path: Path,
) -> None:
    """Cross-check every record in *extracted_path* using seed IDs, write to *output_path*."""
    seeds_raw = json.loads(seeds_path.read_text(encoding="utf-8"))
    seed_lookup = {
        s["drug_name_generic"].lower(): s for s in seeds_raw
    }

    records = [
        ExtractedTriple.model_validate_json(line)
        for line in extracted_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    table = Table(title="Cross-Validation Results", show_lines=True)
    table.add_column("Drug", style="cyan")
    table.add_column("ChEMBL", style="green")
    table.add_column("DrugBank", style="green")
    table.add_column("Discrepancies", style="yellow")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for record in records:
            seed = seed_lookup.get(record.triple.drug_name_generic.lower(), {})
            updated, disc = cross_check_record(
                record,
                chembl_id=seed.get("chembl_id"),
                drugbank_id=seed.get("drugbank_id"),
            )
            fh.write(updated.model_dump_json() + "\n")
            table.add_row(
                record.triple.drug_name_generic,
                "✓" if updated.metadata.chembl_validated else "–",
                "✓" if updated.metadata.drugbank_validated else "–",
                "\n".join(disc) if disc else "none",
            )

    console.print(table)
    console.print(f"[green]Cross-checked {len(records)} records → {output_path}[/green]")
