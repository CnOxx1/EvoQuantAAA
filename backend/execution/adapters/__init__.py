from __future__ import annotations

from execution.adapters.base import AdapterContext, ExecutionAdapter
from execution.adapters.broker_stub import BrokerStubAdapter
from execution.adapters.paper_adapter import PaperAdapter

_ADAPTERS: dict[str, ExecutionAdapter] = {
    PaperAdapter.kind: PaperAdapter(),
    BrokerStubAdapter.kind: BrokerStubAdapter(),
}

ADAPTER_KINDS: tuple[str, ...] = tuple(sorted(_ADAPTERS.keys()))


def get_adapter(kind: str) -> ExecutionAdapter:
    key = (kind or "paper").strip().lower()
    if key not in _ADAPTERS:
        raise KeyError(
            f"未知 execution adapter={kind!r}；可选: {', '.join(ADAPTER_KINDS)}"
        )
    return _ADAPTERS[key]


def list_adapters() -> list[dict[str, str]]:
    return [
        {
            "kind": k,
            "fills": "yes" if k == "paper" else "never",
            "note": "paper 即时撮合"
            if k == "paper"
            else "dry-run 拒单骨架，无网络/无密钥",
        }
        for k in ADAPTER_KINDS
    ]


__all__ = [
    "ADAPTER_KINDS",
    "AdapterContext",
    "ExecutionAdapter",
    "get_adapter",
    "list_adapters",
]
