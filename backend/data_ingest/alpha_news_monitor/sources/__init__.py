from data_ingest.alpha_news_monitor.sources.akshare_src import AkshareNewsSource
from data_ingest.alpha_news_monitor.sources.base import NewsSource
from data_ingest.alpha_news_monitor.sources.mock import MockNewsSource


def get_source(name: str) -> NewsSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockNewsSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareNewsSource()
    raise ValueError(f"未知 alpha_news_monitor 源: {name}")


__all__ = ["AkshareNewsSource", "MockNewsSource", "NewsSource", "get_source"]
