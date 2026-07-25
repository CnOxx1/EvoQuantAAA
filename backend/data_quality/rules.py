from __future__ import annotations

from collections import defaultdict
from typing import Any

from data_quality.corp_action_check import corp_action_adj_check
from data_quality.models import RuleOutcome


def run_core_rules(
    *,
    equity_rows: list[dict[str, Any]],
    index_rows: list[dict[str, Any]],
    calendar_open_dates: set[str] | None,
    expected_symbols: list[str],
    expected_indexes: list[str],
    corp_actions: list[dict[str, Any]] | None = None,
) -> list[RuleOutcome]:
    outcomes: list[RuleOutcome] = []
    outcomes.append(_equity_nonempty(equity_rows, expected_symbols))
    outcomes.append(_index_nonempty(index_rows, expected_indexes))
    outcomes.append(_adj_complete(equity_rows))
    outcomes.append(_price_positive(equity_rows))
    outcomes.append(_ret_coverage(equity_rows))
    outcomes.append(_mask_consistency(equity_rows))
    outcomes.append(_ohlc_order(equity_rows))
    outcomes.append(_extreme_return(equity_rows))
    outcomes.append(_calendar_align(equity_rows, calendar_open_dates))
    outcomes.append(
        corp_action_adj_check(
            corp_actions=corp_actions or [],
            equity_rows=equity_rows,
        )
    )
    return outcomes


def _equity_nonempty(rows: list[dict[str, Any]], expected: list[str]) -> RuleOutcome:
    symbols = sorted({str(r["symbol"]) for r in rows})
    missing = [s for s in expected if s not in symbols] if expected else []
    ok = len(rows) > 0 and not missing
    return RuleOutcome(
        rule_code="equity_nonempty",
        severity="error",
        status="pass" if ok else "fail",
        message="processed equity 有数据" if ok else "processed equity 缺失或标的不全",
        detail={"rows": len(rows), "symbols": symbols, "missing": missing},
    )


def _index_nonempty(rows: list[dict[str, Any]], expected: list[str]) -> RuleOutcome:
    indexes = sorted({str(r["index_symbol"]) for r in rows})
    want = expected or ["000300"]
    missing = [s for s in want if s not in indexes]
    ok = len(rows) > 0 and not missing
    return RuleOutcome(
        rule_code="index_nonempty",
        severity="error",
        status="pass" if ok else "fail",
        message="processed index 有数据" if ok else "processed index 缺失",
        detail={"rows": len(rows), "indexes": indexes, "missing": missing},
    )


def _adj_complete(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = [
        {"symbol": r["symbol"], "trade_date": r["trade_date"]}
        for r in rows
        if r.get("adj_close") is None or r.get("adj_factor") is None
    ]
    ok = not bad
    return RuleOutcome(
        rule_code="adj_complete",
        severity="error",
        status="pass" if ok else "fail",
        message="复权字段齐全" if ok else f"缺复权字段 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _price_positive(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = []
    for r in rows:
        close = r.get("close")
        adj = r.get("adj_close")
        if close is None or adj is None or float(close) <= 0 or float(adj) <= 0:
            bad.append(
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"],
                    "close": close,
                    "adj_close": adj,
                }
            )
    ok = not bad
    return RuleOutcome(
        rule_code="price_positive",
        severity="error",
        status="pass" if ok else "fail",
        message="价格为正" if ok else f"非正价格 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _ret_coverage(rows: list[dict[str, Any]]) -> RuleOutcome:
    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_sym[str(r["symbol"])].append(r)
    problems = []
    for sym, group in by_sym.items():
        group = sorted(group, key=lambda x: str(x["trade_date"]))
        if not group:
            continue
        # 首日允许 ret 为空；其后不得为空
        for i, r in enumerate(group):
            if i == 0:
                continue
            if r.get("ret_1d") is None:
                problems.append({"symbol": sym, "trade_date": r["trade_date"]})
    ok = not problems
    return RuleOutcome(
        rule_code="ret_coverage",
        severity="error",
        status="pass" if ok else "fail",
        message="日收益覆盖正常" if ok else f"ret_1d 缺失 {len(problems)} 行",
        detail={"bad_count": len(problems), "sample": problems[:10]},
    )


def _mask_consistency(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = []
    for r in rows:
        sus = int(r.get("is_suspended") or 0)
        up = int(r.get("is_limit_up") or 0)
        dn = int(r.get("is_limit_down") or 0)
        can_buy = int(r.get("can_buy") or 0)
        can_sell = int(r.get("can_sell") or 0)
        expect_buy = 0 if (sus or up) else 1
        expect_sell = 0 if (sus or dn) else 1
        if can_buy != expect_buy or can_sell != expect_sell:
            bad.append(
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"],
                    "is_suspended": sus,
                    "is_limit_up": up,
                    "is_limit_down": dn,
                    "can_buy": can_buy,
                    "can_sell": can_sell,
                }
            )
    ok = not bad
    return RuleOutcome(
        rule_code="mask_consistency",
        severity="error",
        status="pass" if ok else "fail",
        message="可成交掩码一致" if ok else f"掩码不一致 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _ohlc_order(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = []
    for r in rows:
        o, h, l, c = r.get("open"), r.get("high"), r.get("low"), r.get("close")
        if None in (o, h, l, c):
            continue
        fo, fh, fl, fc = float(o), float(h), float(l), float(c)
        if fl > min(fo, fc) + 1e-9 or fh < max(fo, fc) - 1e-9 or fl > fh + 1e-9:
            bad.append(
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"],
                    "ohlc": [fo, fh, fl, fc],
                }
            )
    # warn：源脏数据常见，不阻断 CORE
    ok = not bad
    return RuleOutcome(
        rule_code="ohlc_order",
        severity="warn",
        status="pass" if ok else "fail",
        message="OHLC 顺序正常" if ok else f"OHLC 异常 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _extreme_return(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = []
    for r in rows:
        ret = r.get("ret_1d")
        if ret is None:
            continue
        if abs(float(ret)) > 0.22:
            bad.append(
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"],
                    "ret_1d": float(ret),
                }
            )
    ok = not bad
    return RuleOutcome(
        rule_code="extreme_return",
        severity="warn",
        status="pass" if ok else "fail",
        message="无极端日收益" if ok else f"|ret|>22% 共 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _calendar_align(
    rows: list[dict[str, Any]], open_dates: set[str] | None
) -> RuleOutcome:
    if not open_dates:
        return RuleOutcome(
            rule_code="calendar_align",
            severity="warn",
            status="pass",
            message="无日历数据，跳过对齐检查",
            detail={"skipped": True},
        )
    bad = []
    for r in rows:
        d = str(r["trade_date"])[:10]
        if d not in open_dates:
            bad.append({"symbol": r["symbol"], "trade_date": d})
    ok = not bad
    return RuleOutcome(
        rule_code="calendar_align",
        severity="warn",
        status="pass" if ok else "fail",
        message="交易日落在开市日历内" if ok else f"非开市日 {len(bad)} 行",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )
