from __future__ import annotations

from typing import Any

from execution.adapters.base import AdapterContext, ExecutionAdapter
from execution.paper import simulate_paper_fills


class PaperAdapter:
    """纸面即时撮合（现有 simulate_paper_fills）。"""

    kind = "paper"

    def execute(
        self, intents: list[dict[str, Any]], ctx: AdapterContext
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return simulate_paper_fills(
            intents=intents,
            cost=ctx.cost,
            trade_date=ctx.trade_date,
            cash=ctx.cash,
            lot_size=ctx.lot_size,
        )


# 类型提示用
_: ExecutionAdapter = PaperAdapter()
