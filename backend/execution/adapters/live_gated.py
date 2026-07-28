from __future__ import annotations

"""
live_gated：实盘路径骨架（fail-closed）。

行为：
1. 未武装 ASHARE_ALLOW_LIVE → 全部拒单 live_env_not_armed
2. 已武装但仍无券商 SDK → 全部拒单 live_sdk_not_configured
3. 永不产生 fill；不读密钥；不发起网络

真实券商 SDK 须另文件实现，且须 DB allow_fills=1 + 本闸门武装后才可成交。
"""

from typing import Any

from execution.adapters.base import AdapterContext, ExecutionAdapter
from execution.adapters.live_gate import (
    LIVE_ENV_NOT_ARMED,
    LIVE_SDK_NOT_CONFIGURED,
    is_live_armed,
)


class LiveGatedAdapter:
    kind = "live_gated"

    def execute(
        self, intents: list[dict[str, Any]], ctx: AdapterContext
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        armed = is_live_armed()
        reason = LIVE_SDK_NOT_CONFIGURED if armed else LIVE_ENV_NOT_ARMED
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
                    "reason": reason,
                }
            )
        _ = ctx
        return orders, []


_: ExecutionAdapter = LiveGatedAdapter()
