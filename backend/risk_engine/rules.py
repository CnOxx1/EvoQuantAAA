from __future__ import annotations

"""事前硬规则（纯函数）：返回 breach 列表；空=通过。"""

from typing import Any

from risk_engine.models import RiskLimits


def evaluate_portfolio(
    *,
    positions: list[dict[str, Any]],
    nav: float,
    invested_value: float | None,
    kill_switch_on: bool,
    limits: RiskLimits,
) -> list[dict[str, Any]]:
    breaches: list[dict[str, Any]] = []

    if kill_switch_on:
        breaches.append(
            {
                "code": "KILL_SWITCH_ON",
                "severity": "error",
                "message": "Kill Switch 开启，禁止放行",
            }
        )

    if nav is None or nav <= 0:
        breaches.append(
            {
                "code": "INVALID_NAV",
                "severity": "error",
                "message": "nav 无效",
            }
        )
        return breaches

    active = [
        p
        for p in positions
        if float(p.get("target_shares") or 0) > 0
        or float(p.get("target_weight") or 0) > 0
    ]
    n = len(active)
    if n < int(limits.min_names):
        breaches.append(
            {
                "code": "MIN_NAMES",
                "severity": "error",
                "message": f"持仓数 {n} < min_names={limits.min_names}",
                "value": n,
            }
        )
    if n > int(limits.max_names):
        breaches.append(
            {
                "code": "MAX_NAMES",
                "severity": "error",
                "message": f"持仓数 {n} > max_names={limits.max_names}",
                "value": n,
            }
        )

    for p in active:
        w = float(p.get("target_weight") or 0.0)
        if w > float(limits.max_single_weight) + 1e-9:
            breaches.append(
                {
                    "code": "MAX_SINGLE_WEIGHT",
                    "severity": "error",
                    "symbol": str(p.get("symbol")),
                    "message": (
                        f"单票权重 {w:.4f} > max={limits.max_single_weight}"
                    ),
                    "value": w,
                }
            )
        cb = p.get("can_buy")
        if cb is not None and int(cb) != 1 and float(p.get("target_shares") or 0) > 0:
            breaches.append(
                {
                    "code": "CANNOT_BUY",
                    "severity": "error",
                    "symbol": str(p.get("symbol")),
                    "message": "目标股数>0 但 can_buy!=1",
                }
            )
        sh = float(p.get("target_shares") or 0)
        lot = max(1, int(limits.lot_size or 100))
        if sh > 0 and abs(sh % lot) > 1e-9:
            breaches.append(
                {
                    "code": "LOT_SIZE",
                    "severity": "error",
                    "symbol": str(p.get("symbol")),
                    "message": f"股数 {sh} 非整手(lot={lot})",
                    "value": sh,
                }
            )

    invested = (
        float(invested_value)
        if invested_value is not None
        else sum(float(p.get("target_value") or 0) for p in active)
    )
    gross = invested / nav if nav > 0 else 0.0
    if gross > float(limits.max_gross_exposure) + 1e-9:
        breaches.append(
            {
                "code": "MAX_GROSS_EXPOSURE",
                "severity": "error",
                "message": (
                    f"总敞口 {gross:.4f} > max={limits.max_gross_exposure}"
                ),
                "value": gross,
            }
        )

    return breaches
