from data_ingest.core_ref.sources.akshare_src import AkshareCoreRefSource
from data_ingest.core_ref.sources.base import CoreRefSource
from data_ingest.core_ref.sources.mock import MockCoreRefSource


def get_source(name: str) -> CoreRefSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockCoreRefSource()
    if key in {"akshare", "eastmoney"}:
        # eastmoney 别名：底层同样走 akshare 封装的东财/交易所接口
        return AkshareCoreRefSource()
    if key == "tushare":
        raise NotImplementedError(
            "core_ref 源 'tushare' 尚未实现，请使用 --source akshare 或 mock"
        )
    raise ValueError(f"未知 core_ref 源: {name}")


__all__ = [
    "AkshareCoreRefSource",
    "CoreRefSource",
    "MockCoreRefSource",
    "get_source",
]
