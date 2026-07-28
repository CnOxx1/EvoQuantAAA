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

    # 行业集中度（需 position.industry_code）
    if limits.max_industry_weight is not None:
        by_ind: dict[str, float] = {}
        missing_ind = 0
        for p in active:
            val = float(p.get("target_value") or 0.0)
            if val <= 0:
                continue
            ind = str(p.get("industry_code") or "").strip()
            if not ind:
                missing_ind += 1
                continue
            by_ind[ind] = by_ind.get(ind, 0.0) + val
        if missing_ind:
            breaches.append(
                {
                    "code": "MISSING_INDUSTRY",
                    "severity": "error",
                    "message": f"{missing_ind} 只标的缺少 industry_code",
                    "value": missing_ind,
                }
            )
        max_iw = float(limits.max_industry_weight)
        for ind, val in by_ind.items():
            w = val / nav
            if w > max_iw + 1e-9:
                breaches.append(
                    {
                        "code": "MAX_INDUSTRY_WEIGHT",
                        "severity": "error",
                        "industry_code": ind,
                        "message": (
                            f"行业 {ind} 权重 {w:.4f} > max={max_iw}"
                        ),
                        "value": w,
                    }
                )

    # ADV 参与度：target_value / adv_20
    if limits.max_adv_participation is not None:
        max_part = float(limits.max_adv_participation)
        for p in active:
            val = float(p.get("target_value") or 0.0)
            if val <= 0:
                continue
            adv = p.get("adv_20")
            if adv is None or float(adv) <= 0:
                breaches.append(
                    {
                        "code": "MISSING_ADV",
                        "severity": "error",
                        "symbol": str(p.get("symbol")),
                        "message": "缺少有效 ADV（20 日均成交额）",
                    }
                )
                continue
            part = val / float(adv)
            if part > max_part + 1e-9:
                breaches.append(
                    {
                        "code": "MAX_ADV_PARTICIPATION",
                        "severity": "error",
                        "symbol": str(p.get("symbol")),
                        "message": (
                            f"ADV 参与度 {part:.4f} > max={max_part}"
                        ),
                        "value": part,
                    }
                )

    return breaches


def evaluate_account_book(
    *,
    position_books: list[list[dict[str, Any]]],
    account_nav: float,
    limits: RiskLimits,
) -> list[dict[str, Any]]:
    """
    同账户多策略合并敞口：按 symbol 汇总 target_value，相对账户 NAV 校验。
    """
    breaches: list[dict[str, Any]] = []
    if account_nav is None or account_nav <= 0:
        breaches.append(
            {
                "code": "INVALID_ACCOUNT_NAV",
                "severity": "error",
                "message": "账户 nav 无效",
            }
        )
        return breaches

    by_sym: dict[str, float] = {}
    for book in position_books:
        for p in book:
            val = float(p.get("target_value") or 0.0)
            if val <= 0:
                continue
            sym = str(p.get("symbol") or "")
            if not sym:
                continue
            by_sym[sym] = by_sym.get(sym, 0.0) + val

    invested = sum(by_sym.values())
    gross = invested / account_nav
    if gross > float(limits.max_gross_exposure) + 1e-9:
        breaches.append(
            {
                "code": "ACCOUNT_MAX_GROSS_EXPOSURE",
                "severity": "error",
                "message": (
                    f"账户合并敞口 {gross:.4f} > max={limits.max_gross_exposure}"
                ),
                "value": gross,
            }
        )

    for sym, val in by_sym.items():
        w = val / account_nav
        if w > float(limits.max_single_weight) + 1e-9:
            breaches.append(
                {
                    "code": "ACCOUNT_MAX_SINGLE_WEIGHT",
                    "severity": "error",
                    "symbol": sym,
                    "message": (
                        f"账户合并单票权重 {w:.4f} > max={limits.max_single_weight}"
                    ),
                    "value": w,
                }
            )

    # 账户合并行业集中度
    if limits.max_industry_weight is not None:
        by_ind: dict[str, float] = {}
        missing_ind = 0
        for book in position_books:
            for p in book:
                val = float(p.get("target_value") or 0.0)
                if val <= 0:
                    continue
                ind = str(p.get("industry_code") or "").strip()
                if not ind:
                    missing_ind += 1
                    continue
                by_ind[ind] = by_ind.get(ind, 0.0) + val
        if missing_ind:
            breaches.append(
                {
                    "code": "ACCOUNT_MISSING_INDUSTRY",
                    "severity": "error",
                    "message": f"账户合并 {missing_ind} 条腿缺少 industry_code",
                    "value": missing_ind,
                }
            )
        max_iw = float(limits.max_industry_weight)
        for ind, val in by_ind.items():
            w = val / account_nav
            if w > max_iw + 1e-9:
                breaches.append(
                    {
                        "code": "ACCOUNT_MAX_INDUSTRY_WEIGHT",
                        "severity": "error",
                        "industry_code": ind,
                        "message": (
                            f"账户合并行业 {ind} 权重 {w:.4f} > max={max_iw}"
                        ),
                        "value": w,
                    }
                )

    # 账户合并 ADV：同票市值合计 / ADV
    if limits.max_adv_participation is not None:
        max_part = float(limits.max_adv_participation)
        adv_by_sym: dict[str, float] = {}
        for book in position_books:
            for p in book:
                sym = str(p.get("symbol") or "")
                adv = p.get("adv_20")
                if not sym or adv is None or float(adv) <= 0:
                    continue
                # 取首次有效 ADV（同标的应一致）
                adv_by_sym.setdefault(sym, float(adv))
        for sym, val in by_sym.items():
            adv = adv_by_sym.get(sym)
            if adv is None or adv <= 0:
                breaches.append(
                    {
                        "code": "ACCOUNT_MISSING_ADV",
                        "severity": "error",
                        "symbol": sym,
                        "message": "账户合并缺少有效 ADV",
                    }
                )
                continue
            part = val / adv
            if part > max_part + 1e-9:
                breaches.append(
                    {
                        "code": "ACCOUNT_MAX_ADV_PARTICIPATION",
                        "severity": "error",
                        "symbol": sym,
                        "message": (
                            f"账户合并 ADV 参与度 {part:.4f} > max={max_part}"
                        ),
                        "value": part,
                    }
                )

    return breaches
