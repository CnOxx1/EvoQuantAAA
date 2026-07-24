from data_ingest.alpha_fundamental.sources.akshare_src import AkshareFundamentalSource
from data_ingest.alpha_fundamental.sources.base import FundamentalSource
from data_ingest.alpha_fundamental.sources.mock import MockFundamentalSource


def get_source(name: str) -> FundamentalSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockFundamentalSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareFundamentalSource()
    raise ValueError(f"未知 alpha_fundamental 源: {name}")


__all__ = [
    "AkshareFundamentalSource",
    "FundamentalSource",
    "MockFundamentalSource",
    "get_source",
]
