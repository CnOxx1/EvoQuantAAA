from data_ingest.alpha_contract.sources.akshare_src import AkshareContractSource
from data_ingest.alpha_contract.sources.base import ContractSource
from data_ingest.alpha_contract.sources.mock import MockContractSource


def get_source(name: str) -> ContractSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockContractSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareContractSource()
    raise ValueError(f"未知 alpha_contract 源: {name}")


__all__ = ["AkshareContractSource", "ContractSource", "MockContractSource", "get_source"]
