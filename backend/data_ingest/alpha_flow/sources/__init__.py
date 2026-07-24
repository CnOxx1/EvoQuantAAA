from data_ingest.alpha_flow.sources.akshare_src import AkshareFlowSource
from data_ingest.alpha_flow.sources.base import FlowSource
from data_ingest.alpha_flow.sources.mock import MockFlowSource


def get_source(name: str) -> FlowSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockFlowSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareFlowSource()
    raise ValueError(f"未知 alpha_flow 源: {name}")


__all__ = ["AkshareFlowSource", "FlowSource", "MockFlowSource", "get_source"]
