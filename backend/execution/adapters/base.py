from __future__ import annotations

"""执行适配器协议：意图 → (orders_raw, fills_raw)。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from execution.models import CostSnapshot


@dataclass
class AdapterContext:
    cost: CostSnapshot
    trade_date: str
    cash: float | None = None
    lot_size: int = 100
    meta: dict[str, Any] = field(default_factory=dict)


class ExecutionAdapter(Protocol):
    kind: str

    def execute(
        self, intents: list[dict[str, Any]], ctx: AdapterContext
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """返回与 paper.simulate_paper_fills 同形的 (orders, fills)。"""
        ...
