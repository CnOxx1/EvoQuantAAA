from data_ingest.alpha_relation.sources.akshare_src import AkshareRelationSource
from data_ingest.alpha_relation.sources.base import RelationSource
from data_ingest.alpha_relation.sources.mock import MockRelationSource


def get_source(name: str) -> RelationSource:
    key = (name or "akshare").lower()
    if key == "mock":
        return MockRelationSource()
    if key in {"akshare", "eastmoney"}:
        return AkshareRelationSource()
    raise ValueError(f"未知 alpha_relation 源: {name}")


__all__ = ["AkshareRelationSource", "RelationSource", "MockRelationSource", "get_source"]
