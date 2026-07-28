from __future__ import annotations

"""
broker_stub：柜台适配器骨架。

设计约束（开发机强制）：
- 不发起任何网络/柜台调用
- 不读取券商密钥
- 默认将全部可执行意图拒单（dry_run_no_live），不产生 fill
- 真实 live 适配器须另实现，并显式环境开关（本 stub 永不成交）
"""

from typing import Any

from execution.adapters.base import AdapterContext, ExecutionAdapter


REJECT_REASON = "dry_run_no_live"


class BrokerStubAdapter:
    kind = "broker_stub"

    def execute(
        self, intents: list[dict[str, Any]], ctx: AdapterContext
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        orders: list[dict[str, Any]] = []
        for it in intents:
            side = str(it.get("side") or "")
            qty = float(it.get("qty") or 0)
            if it.get("reject"):
                orders.append(
                    {
                        "symbol": it.get("symbol"),
                        "side": side,
                        "qty": qty,
                        "limit_price": it.get("mid_price"),
                        "status": "REJECTED",
                        "reason": it.get("reason") or "rejected",
                    }
                )
                continue
            orders.append(
                {
                    "symbol": it.get("symbol"),
                    "side": side,
                    "qty": qty,
                    "limit_price": it.get("mid_price"),
                    "status": "REJECTED",
                    "reason": REJECT_REASON,
                }
            )
        # 永不产生成交
        _ = ctx
        return orders, []


_: ExecutionAdapter = BrokerStubAdapter()
