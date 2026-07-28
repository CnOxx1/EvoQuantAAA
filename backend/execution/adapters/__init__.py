from __future__ import annotations

from execution.adapters.base import AdapterContext, ExecutionAdapter
from execution.adapters.broker_stub import BrokerStubAdapter
from execution.adapters.live_gated import LiveGatedAdapter
from execution.adapters.paper_adapter import PaperAdapter

_ADAPTERS: dict[str, ExecutionAdapter] = {
    PaperAdapter.kind: PaperAdapter(),
    BrokerStubAdapter.kind: BrokerStubAdapter(),
    LiveGatedAdapter.kind: LiveGatedAdapter(),
}

ADAPTER_KINDS: tuple[str, ...] = tuple(sorted(_ADAPTERS.keys()))

_NOTES: dict[str, tuple[str, str]] = {
    "paper": ("yes", "paper 即时撮合"),
    "broker_stub": ("never", "dry-run 拒单骨架，无网络/无密钥"),
    "live_gated": (
        "never",
        "须 ASHARE_ALLOW_LIVE；武装后仍无 SDK，fail-closed",
    ),
}


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
            "fills": _NOTES.get(k, ("?", "?"))[0],
            "note": _NOTES.get(k, ("?", "?"))[1],
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
