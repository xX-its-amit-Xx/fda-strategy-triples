"""
Public API contract tests for fda_strategy_triples.load_dataset.

These tests are the integration gate for the stable release artifact.
They must pass before any version is tagged.  Do not mock the release files —
the point is to verify the *actual bundled data*.
"""
from __future__ import annotations

import pytest
import pandas as pd

from fda_strategy_triples import load_dataset, __version__
from fda_strategy_triples.loader import available_versions, LATEST_VERSION
from fda_strategy_triples.extract.schema import ExtractedTriple, MechanismClass


# ── version bookkeeping ────────────────────────────────────────────────────────

class TestVersions:
    def test_latest_version_in_catalogue(self) -> None:
        assert LATEST_VERSION in available_versions()

    def test_v010_available(self) -> None:
        assert "v0.1.0" in available_versions()

    def test_unknown_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown version"):
            load_dataset(version="v99.99.99")


# ── DataFrame mode (default) ──────────────────────────────────────────────────

class TestDataFrame:
    @pytest.fixture(scope="class")
    def df(self) -> pd.DataFrame:
        return load_dataset()

    def test_returns_dataframe(self, df: pd.DataFrame) -> None:
        assert isinstance(df, pd.DataFrame)

    def test_record_count(self, df: pd.DataFrame) -> None:
        assert len(df) == 10, f"Expected 10 records, got {len(df)}"

    def test_required_columns_present(self, df: pd.DataFrame) -> None:
        required = [
            "id",
            "schema_version",
            "drug_name_generic",
            "drug_name_brand",
            "approval_date",
            "indicated_disease",
            "associated_genes",
            "variant_context",
            "molecular_target",
            "mechanism_class",
            "mechanism_summary",
            "primary_citation_pmid",
            "reviewer",
            "reviewed_at",
            "validated",
            "chembl_validated",
            "drugbank_validated",
            "prompt_version",
            "extractor_model",
            "fetch_timestamp",
            "source_apis",
            "confidence_score",
        ]
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Missing columns: {missing}"

    def test_all_records_validated(self, df: pd.DataFrame) -> None:
        assert df["validated"].all(), "Some records have validated=False"

    def test_no_null_generic_names(self, df: pd.DataFrame) -> None:
        assert df["drug_name_generic"].notna().all()
        assert (df["drug_name_generic"].str.len() > 0).all()

    def test_mechanism_class_values_in_vocabulary(self, df: pd.DataFrame) -> None:
        valid = {m.value for m in MechanismClass}
        bad = set(df["mechanism_class"].unique()) - valid
        assert not bad, f"Unknown mechanism_class values: {bad}"

    def test_associated_genes_are_sequences(self, df: pd.DataFrame) -> None:
        # pyarrow list<string> columns deserialise as numpy arrays in pandas,
        # not Python lists — both are valid sequence types for downstream use.
        import numpy as np
        for val in df["associated_genes"]:
            assert isinstance(val, (list, np.ndarray)), (
                f"associated_genes must be list or ndarray, got {type(val)}"
            )
            assert all(isinstance(g, str) for g in val)

    def test_version_pin_works(self) -> None:
        df_pinned = load_dataset(version="v0.1.0")
        assert isinstance(df_pinned, pd.DataFrame)
        assert len(df_pinned) == 10

    def test_default_equals_latest(self) -> None:
        df_default = load_dataset()
        df_latest  = load_dataset(version="latest")
        assert list(df_default["id"]) == list(df_latest["id"])

    def test_confidence_scores_in_range(self, df: pd.DataFrame) -> None:
        scores = df["confidence_score"].dropna()
        assert (scores >= 0.0).all() and (scores <= 1.0).all()


# ── Pydantic mode ─────────────────────────────────────────────────────────────

class TestPydantic:
    @pytest.fixture(scope="class")
    def records(self) -> list[ExtractedTriple]:
        return load_dataset(as_pydantic=True)

    def test_returns_list(self, records: list[ExtractedTriple]) -> None:
        assert isinstance(records, list)

    def test_all_extracted_triple_instances(self, records: list[ExtractedTriple]) -> None:
        assert all(isinstance(r, ExtractedTriple) for r in records)

    def test_record_count(self, records: list[ExtractedTriple]) -> None:
        assert len(records) == 10

    def test_all_validated(self, records: list[ExtractedTriple]) -> None:
        assert all(r.metadata.validated for r in records)

    def test_provenance_reviewer_set(self, records: list[ExtractedTriple]) -> None:
        for r in records:
            assert r.metadata.reviewer, f"reviewer unset for {r.triple.drug_name_generic}"

    def test_provenance_reviewed_at_set(self, records: list[ExtractedTriple]) -> None:
        for r in records:
            assert r.metadata.reviewed_at, f"reviewed_at unset for {r.triple.drug_name_generic}"

    def test_prompt_version_pinned(self, records: list[ExtractedTriple]) -> None:
        for r in records:
            assert r.metadata.prompt_version == "v1.2.0", (
                f"{r.triple.drug_name_generic}: expected prompt v1.2.0, "
                f"got {r.metadata.prompt_version}"
            )

    def test_source_apis_non_empty(self, records: list[ExtractedTriple]) -> None:
        for r in records:
            assert r.metadata.source_apis, f"source_apis empty for {r.triple.drug_name_generic}"

    def test_gene_symbols_uppercase(self, records: list[ExtractedTriple]) -> None:
        for r in records:
            for gene in r.triple.associated_genes:
                assert gene == gene.upper(), f"Non-uppercase gene symbol: {gene}"

    def test_ids_unique(self, records: list[ExtractedTriple]) -> None:
        ids = [r.id for r in records]
        assert len(ids) == len(set(ids)), "Duplicate IDs in dataset"

    def test_schema_version_consistent(self, records: list[ExtractedTriple]) -> None:
        versions = {r.schema_version for r in records}
        assert len(versions) == 1, f"Mixed schema versions: {versions}"
        assert "1.0.0" in versions

    # ── spot-checks on specific records ──────────────────────────────────────

    def test_nusinersen_present(self, records: list[ExtractedTriple]) -> None:
        names = [r.triple.drug_name_generic for r in records]
        assert "nusinersen" in names

    def test_nusinersen_mechanism_class(self, records: list[ExtractedTriple]) -> None:
        rec = next(r for r in records if r.triple.drug_name_generic == "nusinersen")
        assert rec.triple.mechanism_class == MechanismClass.aso

    def test_ivacaftor_gene(self, records: list[ExtractedTriple]) -> None:
        rec = next(r for r in records if r.triple.drug_name_generic == "ivacaftor")
        assert "CFTR" in rec.triple.associated_genes

    def test_exagamglogene_is_gene_therapy(self, records: list[ExtractedTriple]) -> None:
        rec = next(
            (r for r in records if "exagamglogene" in r.triple.drug_name_generic), None
        )
        assert rec is not None, "exagamglogene autotemcel not found"
        assert rec.triple.mechanism_class == MechanismClass.gene_therapy
