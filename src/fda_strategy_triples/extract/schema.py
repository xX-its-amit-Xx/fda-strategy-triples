"""
Pydantic v2 schemas for fda-strategy-triples.

Each record encodes one (gene → variant_context → FDA drug → molecular_target →
mechanism) tuple extracted from FDA structured product labels and cross-validated
against ChEMBL and DrugBank.  Records in data/validated/ have been signed off
by a human domain expert.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"


class MechanismClass(str, Enum):
    """Controlled vocabulary for molecular mechanism of action."""
    inhibitor          = "inhibitor"
    agonist            = "agonist"
    chaperone          = "chaperone"
    aso                = "ASO"
    sirna              = "siRNA"
    gene_therapy       = "gene_therapy"
    enzyme_replacement = "enzyme_replacement"
    monoclonal_antibody = "monoclonal_antibody"
    modulator          = "modulator"
    other              = "other"


class FDATriple(BaseModel):
    """
    Core scientific record: one drug–gene–variant–target–mechanism association.

    All fields are extracted from the FDA structured product label (SPL) or
    derived from cross-validation against ChEMBL / DrugBank.  See
    ValidationMetadata for full provenance.
    """
    drug_name_generic: str = Field(
        description="INN/USAN generic name (lowercase, as filed with FDA)"
    )
    drug_name_brand: str = Field(
        description="FDA proprietary/trade name"
    )
    approval_date: Optional[str] = Field(
        default=None,
        description=(
            "ISO 8601 date of initial FDA approval (e.g. '2016-12-23'), "
            "or the string 'investigational' for pipeline compounds."
        ),
    )
    indicated_disease: str = Field(
        description="Primary rare-disease indication as stated in the SPL Indications section."
    )
    associated_genes: list[str] = Field(
        description=(
            "HGNC official gene symbols causally linked to the indication. "
            "Includes both the disease gene and the drug-target gene when distinct "
            "(e.g. SMN1 for disease, SMN2 for ASO target)."
        ),
        min_length=1,
    )
    variant_context: str = Field(
        description=(
            "Specific variant class or mutation context that defines patient "
            "eligibility or mechanistic relevance. "
            "Examples: 'G551D gating mutation in CFTR', "
            "'biallelic SMN1 deletion or mutation', "
            "'frameshift c.428dupC in MUC1'."
        )
    )
    molecular_target: str = Field(
        description=(
            "Primary molecular target of the drug. Use 'UniProt_accession (SYMBOL)' "
            "format when available (e.g. 'P13569 (CFTR)'); otherwise a descriptive name."
        )
    )
    mechanism_summary: str = Field(
        description=(
            "1–2 sentence plain-English mechanistic description accurate enough "
            "for a domain-expert audit."
        )
    )
    mechanism_class: MechanismClass = Field(
        description="Controlled-vocabulary mechanism class."
    )
    primary_citation_pmid: Optional[str] = Field(
        default=None,
        description=(
            "PubMed ID of the pivotal clinical trial underpinning FDA approval. "
            "Omit leading 'PMID:' prefix; digits only."
        ),
        pattern=r"^\d+$",
    )

    # ── validators ────────────────────────────────────────────────────────────

    @field_validator("associated_genes", mode="before")
    @classmethod
    def normalize_gene_symbols(cls, v: list[str]) -> list[str]:
        return [g.strip().upper() for g in v]

    @field_validator("drug_name_generic", mode="before")
    @classmethod
    def lowercase_generic(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("primary_citation_pmid", mode="before")
    @classmethod
    def strip_pmid_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().upper().lstrip("PMID:").strip()
        return cleaned if cleaned else None


class ValidationMetadata(BaseModel):
    """
    Full provenance trail for one record.

    Per-row provenance is a dataset quality requirement: every field must be
    populated before validated=True may be set.
    """
    source_apis: list[str] = Field(
        description="Ordered list of APIs queried to build this record (e.g. ['openfda', 'dailymed'])."
    )
    fetch_timestamp: str = Field(
        description="ISO 8601 UTC timestamp of the most recent raw-data fetch."
    )
    prompt_version: str = Field(
        description="Extractor prompt version (e.g. 'v1.2.0') used to produce this record."
    )
    extractor_model: str = Field(
        description="Anthropic model ID used for extraction (e.g. 'claude-sonnet-4-6')."
    )
    chembl_validated: bool = Field(
        default=False,
        description="True if mechanism/target have been confirmed against a ChEMBL drug record."
    )
    drugbank_validated: bool = Field(
        default=False,
        description="True if mechanism/target have been confirmed against a DrugBank record."
    )
    discrepancies: list[str] = Field(
        default_factory=list,
        description=(
            "Human-readable notes on cross-validation mismatches between sources. "
            "Empty list means no discrepancies detected."
        ),
    )
    reviewer: Optional[str] = Field(
        default=None,
        description="GitHub username or email of the human reviewer who signed off this record."
    )
    reviewed_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 UTC timestamp at which human review was completed."
    )
    validated: bool = Field(
        default=False,
        description=(
            "True only after a human domain expert has reviewed and confirmed "
            "the triple.  Records with validated=False must not be used in "
            "downstream applications without further review."
        )
    )

    @model_validator(mode="after")
    def require_reviewer_if_validated(self) -> "ValidationMetadata":
        if self.validated and not self.reviewer:
            raise ValueError("validated=True requires reviewer to be set")
        if self.validated and not self.reviewed_at:
            raise ValueError("validated=True requires reviewed_at to be set")
        return self


class ExtractedTriple(BaseModel):
    """
    Complete record as stored in data/extracted/ (unvalidated) and
    data/validated/ (human-reviewed).
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Stable UUID4 identifier; preserved across pipeline reruns."
    )
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="Schema version used to create this record."
    )
    triple: FDATriple
    metadata: ValidationMetadata
    raw_label_url: Optional[str] = Field(
        default=None,
        description="Direct URL to the DailyMed / OpenFDA source label used for extraction."
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Self-reported LLM extraction confidence in [0, 1]. "
            "Not a calibrated probability — treat as a coarse signal."
        )
    )


class DrugSeed(BaseModel):
    """
    Minimal input record driving the ETL pipeline for one drug.
    Stored in data/seeds/drug_seeds.json.
    """
    drug_name_generic: str
    drug_name_brand: str
    openfda_set_id: Optional[str] = Field(
        default=None,
        description="OpenFDA label set-id UUID for direct lookup."
    )
    dailymed_set_id: Optional[str] = Field(
        default=None,
        description="DailyMed setid for direct SPL retrieval."
    )
    chembl_id: Optional[str] = Field(
        default=None,
        description="ChEMBL compound ID (e.g. 'CHEMBL1950026')."
    )
    drugbank_id: Optional[str] = Field(
        default=None,
        description="DrugBank accession (e.g. 'DB09260')."
    )
    mechanism_hint: Optional[MechanismClass] = Field(
        default=None,
        description="Known mechanism class; speeds up extraction prompt."
    )
    gene_hints: list[str] = Field(
        default_factory=list,
        description="Known associated HGNC gene symbols; seeds the extractor prompt."
    )
    is_investigational: bool = Field(
        default=False,
        description="True for pipeline/pre-approval compounds."
    )
    needs_manual_verification: bool = Field(
        default=False,
        description="Flag compounds where drug identity is uncertain."
    )
    notes: Optional[str] = None
