from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from data_quality.models import RuleOutcome


def _parse_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def theoretical_ex_price(
    prev_close: float, *, cash_per_share: float, share_factor: float
) -> float:
    """P_ex = (P_prev - D) / (1 + S+T)，share_factor = bonus/10 + transfer/10。"""
    denom = 1.0 + share_factor
    if denom <= 0:
        return prev_close
    return (prev_close - cash_per_share) / denom


def corp_action_adj_check(
    *,
    corp_actions: list[dict[str, Any]],
    equity_rows: list[dict[str, Any]],
    tolerance: float = 0.02,
) -> RuleOutcome:
    """
    除权日未复权 close 与理论除权价偏差 ≤ 2%。
    缺前收/缺 payload 比例 → skip（不计入 fail）。
    """
    by_sym_date: dict[tuple[str, str], float] = {}
    dates_by_sym: dict[str, list[str]] = defaultdict(list)
    for r in equity_rows:
        if r.get("close") is None:
            continue
        sym = str(r["symbol"])
        d = str(r["trade_date"])[:10]
        by_sym_date[(sym, d)] = float(r["close"])
        dates_by_sym[sym].append(d)
    for sym in dates_by_sym:
        dates_by_sym[sym] = sorted(set(dates_by_sym[sym]))

    # 合并同日 DIVIDEND+BONUS
    by_ex: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"cash": 0.0, "share": 0.0}
    )
    for a in corp_actions:
        sym = str(a["symbol"])
        ex = str(a["ex_date"])[:10]
        payload = _parse_payload(a.get("raw_payload"))
        at = str(a.get("action_type") or "").upper()
        if at == "DIVIDEND":
            if payload.get("cash") is not None:
                by_ex[(sym, ex)]["cash"] += float(payload["cash"])
            elif payload.get("cash_per_10") is not None:
                by_ex[(sym, ex)]["cash"] += float(payload["cash_per_10"]) / 10.0
        elif at == "BONUS":
            bonus = float(payload.get("bonus_ratio_per_10") or 0)
            transfer = float(payload.get("transfer_ratio_per_10") or 0)
            total = payload.get("bonus_total_per_10")
            if total is not None and bonus == 0 and transfer == 0:
                by_ex[(sym, ex)]["share"] += float(total) / 10.0
            else:
                by_ex[(sym, ex)]["share"] += (bonus + transfer) / 10.0

    checked = 0
    bad: list[dict[str, Any]] = []
    skipped = 0
    for (sym, ex), ratios in by_ex.items():
        dates = dates_by_sym.get(sym) or []
        if (sym, ex) not in by_sym_date:
            skipped += 1
            continue
        prev_dates = [d for d in dates if d < ex]
        if not prev_dates:
            skipped += 1
            continue
        prev = prev_dates[-1]
        prev_close = by_sym_date.get((sym, prev))
        ex_close = by_sym_date.get((sym, ex))
        if prev_close is None or ex_close is None or prev_close <= 0:
            skipped += 1
            continue
        if ratios["cash"] == 0 and ratios["share"] == 0:
            skipped += 1
            continue
        theo = theoretical_ex_price(
            prev_close, cash_per_share=ratios["cash"], share_factor=ratios["share"]
        )
        if theo <= 0:
            skipped += 1
            continue
        checked += 1
        dev = abs(ex_close - theo) / theo
        if dev > tolerance:
            bad.append(
                {
                    "symbol": sym,
                    "ex_date": ex,
                    "prev_close": prev_close,
                    "close": ex_close,
                    "theoretical": theo,
                    "deviation": dev,
                }
            )

    if checked == 0:
        return RuleOutcome(
            rule_code="corp_action_adj_check",
            severity="warn",
            status="pass",
            message="无可用除权样本，跳过",
            detail={"checked": 0, "skipped": skipped},
        )
    ok = not bad
    return RuleOutcome(
        rule_code="corp_action_adj_check",
        severity="warn",
        status="pass" if ok else "fail",
        message="除权价交叉校验通过" if ok else f"除权偏差>2% 共 {len(bad)} 条",
        detail={"checked": checked, "bad_count": len(bad), "sample": bad[:10], "skipped": skipped},
    )
