"""
Public dataset loader for fda-strategy-triples.

    from fda_strategy_triples import load_dataset
    df  = load_dataset()                        # pandas DataFrame
    recs = load_dataset(as_pydantic=True)       # list[ExtractedTriple]
    df  = load_dataset(version="v0.1.0")        # pin a specific release

Data files live inside the installed package under releases/<version>/.
They are generated from data/validated/validated_triples.jsonl and frozen
per release so imports are reproducible regardless of the git working tree.
"""
from __future__ import annotations

import importlib.resources as _pkg_resources
from pathlib import Path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    import pandas as pd
    from fda_strategy_triples.extract.schema import ExtractedTriple

# Catalogue of shipped releases; bump on every release.
_RELEASES: list[str] = ["v0.1.0"]
LATEST_VERSION: str = _RELEASES[-1]


def _release_file(version: str, filename: str) -> Path:
    """Return an absolute Path to *filename* inside the package release dir."""
    ref = (
        _pkg_resources.files("fda_strategy_triples")
        .joinpath("releases")
        .joinpath(version)
        .joinpath(filename)
    )
    # as_file() materialises the Traversable to a real filesystem path,
    # which is necessary for pandas / pyarrow when installed as a zip egg.
    ctx = _pkg_resources.as_file(ref)
    # We enter the context here and rely on the caller to read the file
    # synchronously before this function returns.  For our use-case (reading
    # Parquet / JSONL at import time) that is always true.
    return ctx.__enter__()


def available_versions() -> list[str]:
    """Return list of release versions bundled with the installed package."""
    return list(_RELEASES)


def load_dataset(
    version: str = "latest",
    *,
    as_pydantic: bool = False,
) -> "Union[pd.DataFrame, list[ExtractedTriple]]":
    """
    Load the validated FDA strategy triples for *version*.

    Parameters
    ----------
    version : str
        Release tag to load (e.g. ``"v0.1.0"``).  Use ``"latest"`` (default)
        to load the most recent bundled release.
    as_pydantic : bool
        If ``True``, return a ``list[ExtractedTriple]`` (full provenance
        metadata intact).  If ``False`` (default), return a
        ``pandas.DataFrame`` with flat columns.

    Returns
    -------
    pandas.DataFrame | list[ExtractedTriple]

    Examples
    --------
    >>> from fda_strategy_triples import load_dataset
    >>> df = load_dataset()
    >>> df[["drug_name_generic", "mechanism_class", "associated_genes"]].head()

    >>> records = load_dataset(as_pydantic=True)
    >>> records[0].metadata.reviewer
    'shenoy.am@husky.neu.edu'
    """
    if version == "latest":
        version = LATEST_VERSION

    if version not in _RELEASES:
        raise ValueError(
            f"Unknown version {version!r}. Available: {_RELEASES}. "
            "Update the package to access newer releases."
        )

    if as_pydantic:
        return _load_pydantic(version)
    return _load_dataframe(version)


def _load_dataframe(version: str) -> "pd.DataFrame":
    import pandas as pd  # lazy; not required at package import time

    path = _release_file(version, "triples.parquet")
    return pd.read_parquet(path)


def _load_pydantic(version: str) -> "list[ExtractedTriple]":
    from fda_strategy_triples.extract.schema import ExtractedTriple

    path = _release_file(version, "triples.jsonl")
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ExtractedTriple.model_validate_json(line) for line in lines if line.strip()]
