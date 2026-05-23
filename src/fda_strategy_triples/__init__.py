"""
fda-strategy-triples — curated gene→variant→drug→target→mechanism dataset.

Public API
----------
    from fda_strategy_triples import load_dataset

    df      = load_dataset()                   # pandas DataFrame
    records = load_dataset(as_pydantic=True)   # list[ExtractedTriple]
    df      = load_dataset(version="v0.1.0")   # pin a release
"""
__version__ = "0.1.0"

from fda_strategy_triples.loader import load_dataset, available_versions, LATEST_VERSION

__all__ = ["load_dataset", "available_versions", "LATEST_VERSION", "__version__"]
