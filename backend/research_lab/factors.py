from __future__ import annotations

"""三个基线因子的纯函数计算（不连库、无未来函数）。"""

from collections import defaultdict
from typing import Any


def _dates_sorted(rows: list[dict[str, Any]], *, key: str = "trade_date") -> list[str]:
    return sorted({str(r[key])[:10] for r in rows})


def compute_mom_20(
    bars: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """MOM_20 = adj_close_t / adj_close_{t-20} - 1（按标的交易日序列，非日历日）。"""
    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        if b.get("adj_close") is None:
            continue
        by_sym[str(b["symbol"])].append(b)

    out: list[dict[str, Any]] = []
    for sym, rows in by_sym.items():
        rows = sorted(rows, key=lambda r: str(r["trade_date"])[:10])
        closes = [float(r["adj_close"]) for r in rows]
        dates = [str(r["trade_date"])[:10] for r in rows]
        for i, d in enumerate(dates):
            if d < start or d > end:
                continue
            j = i - 20
            if j < 0:
                continue
            prev = closes[j]
            if prev == 0:
                continue
            out.append({"symbol": sym, "trade_date": d, "value": closes[i] / prev - 1.0})
    out.sort(key=lambda r: (r["trade_date"], r["symbol"]))
    return out


def _pct_ranks(pe_by_sym: dict[str, float]) -> dict[str, float]:
    """升序 percent rank：最低 PE→0，最高→1；并列取平均秩。"""
    items = sorted(pe_by_sym.items(), key=lambda x: x[1])
    n = len(items)
    if n == 0:
        return {}
    if n == 1:
        return {items[0][0]: 0.0}

    ranks: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0-based
        pct = avg_rank / (n - 1)
        for k in range(i, j + 1):
            ranks[items[k][0]] = pct
        i = j + 1
    return ranks


def compute_val_pe_pct(
    valuations: list[dict[str, Any]],
    *,
    symbols: set[str],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """
    VAL_PE_PCT：当日 Universe 内 PE-TTM 截面分位。
    PE>0 参与排序；PE≤0 归最差档（1.0）；缺失不产出。
    """
    by_date: dict[str, dict[str, float | None]] = defaultdict(dict)
    for r in valuations:
        sym = str(r["symbol"])
        if sym not in symbols:
            continue
        d = str(r["trade_date"])[:10]
        if d < start or d > end:
            continue
        pe = r.get("pe_ttm")
        by_date[d][sym] = None if pe is None else float(pe)

    out: list[dict[str, Any]] = []
    for d in sorted(by_date):
        pe_map = by_date[d]
        valid = {s: pe for s, pe in pe_map.items() if pe is not None and pe > 0}
        ranks = _pct_ranks(valid)
        for sym, pe in pe_map.items():
            if pe is None:
                continue
            if pe <= 0:
                out.append({"symbol": sym, "trade_date": d, "value": 1.0})
            else:
                out.append({"symbol": sym, "trade_date": d, "value": ranks[sym]})
    out.sort(key=lambda r: (r["trade_date"], r["symbol"]))
    return out


def compute_flow_net_5(
    flows: list[dict[str, Any]],
    bars: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """
    FLOW_NET_5 = 近 5 个交易日主力净流入之和 / 近 5 日成交额之和。
    资金优先 flow_type=STOCK_FLOW；成交额用 processed 日线 amount。
    """
    # scope(=symbol), trade_date -> net
    net: dict[tuple[str, str], float] = {}
    for r in flows:
        ft = str(r.get("flow_type") or "")
        if ft not in ("STOCK_FLOW", "STOCK_NORTHBOUND"):
            continue
        sym = str(r["scope"])
        d = str(r["trade_date"])[:10]
        key = (sym, d)
        val = r.get("net_amount")
        if val is None:
            continue
        # STOCK_FLOW 优先覆盖回退源
        if key in net and ft == "STOCK_NORTHBOUND":
            continue
        if ft == "STOCK_FLOW" or key not in net:
            net[key] = float(val)

    amt: dict[tuple[str, str], float] = {}
    by_sym_dates: dict[str, list[str]] = defaultdict(list)
    for b in bars:
        sym = str(b["symbol"])
        d = str(b["trade_date"])[:10]
        a = b.get("amount")
        if a is None:
            continue
        amt[(sym, d)] = float(a)
        by_sym_dates[sym].append(d)

    out: list[dict[str, Any]] = []
    for sym, dates in by_sym_dates.items():
        dates = sorted(set(dates))
        for i, d in enumerate(dates):
            if d < start or d > end:
                continue
            window = dates[max(0, i - 4) : i + 1]
            if len(window) < 5:
                continue
            sum_net = 0.0
            sum_amt = 0.0
            flow_hits = 0
            ok = True
            for wd in window:
                if (sym, wd) not in amt:
                    ok = False
                    break
                sum_amt += amt[(sym, wd)]
                if (sym, wd) in net:
                    sum_net += net[(sym, wd)]
                    flow_hits += 1
            # 无资金流行时不编造 0 因子
            if not ok or sum_amt <= 0 or flow_hits == 0:
                continue
            out.append(
                {"symbol": sym, "trade_date": d, "value": sum_net / sum_amt}
            )
    out.sort(key=lambda r: (r["trade_date"], r["symbol"]))
    return out
