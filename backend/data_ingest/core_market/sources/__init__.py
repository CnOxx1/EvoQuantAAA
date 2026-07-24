from data_ingest.core_market.sources.akshare_src import AkshareCoreMarketSource
from data_ingest.core_market.sources.base import CoreMarketSource
from data_ingest.core_market.sources.mock import MockCoreMarketSource


def get_source(name: str) -> CoreMarketSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockCoreMarketSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareCoreMarketSource()
    raise ValueError(f"未知 core_market 源: {name}")


__all__ = [
    "AkshareCoreMarketSource",
    "CoreMarketSource",
    "MockCoreMarketSource",
    "get_source",
]
