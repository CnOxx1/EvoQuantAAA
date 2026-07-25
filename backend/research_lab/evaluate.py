from __future__ import annotations

"""因子评估：RankIC（t→t+1）与 5 分位分层（纯函数）。"""

from collections import defaultdict
from typing import Any


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = sum((a - mx) ** 2 for a in rx) ** 0.5
    deny = sum((b - my) ** 2 for b in ry) ** 0.5
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def evaluate_factor(
    *,
    factor_rows: list[dict[str, Any]],
    ret_rows: list[dict[str, Any]],
    n_quantiles: int = 5,
) -> dict[str, Any]:
    """
    factor_rows: symbol, trade_date, value
    ret_rows: symbol, trade_date, ret_1d  （trade_date 日的收益 = 相对前日）
    IC：用 t 日因子对 t+1 日 ret_1d（即次日收益）。
    """
    factor_by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for r in factor_rows:
        if r.get("value") is None:
            continue
        factor_by_date[str(r["trade_date"])[:10]][str(r["symbol"])] = float(r["value"])

    ret_by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for r in ret_rows:
        if r.get("ret_1d") is None:
            continue
        ret_by_date[str(r["trade_date"])[:10]][str(r["symbol"])] = float(r["ret_1d"])

    dates = sorted(factor_by_date.keys())
    all_ret_dates = sorted(ret_by_date.keys())
    # factor 日 t → 次一交易日（ret_1d 记在该日 = t→t+1 收益）
    next_map: dict[str, str] = {}
    for d in dates:
        for rd in all_ret_dates:
            if rd > d:
                next_map[d] = rd
                break

    daily_ics: list[float] = []
    # quantile cumulative: list of daily mean next-ret per q
    q_daily: list[list[float]] = [[] for _ in range(n_quantiles)]

    for d in dates:
        nxt = next_map.get(d)
        if not nxt or nxt not in ret_by_date:
            continue
        fmap = factor_by_date[d]
        rmap = ret_by_date[nxt]
        pairs = [(fmap[s], rmap[s]) for s in fmap if s in rmap]
        if len(pairs) < 3:
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        ic = _spearman(xs, ys)
        if ic is not None:
            daily_ics.append(ic)

        # 5 分位：按因子升序，Q1=低因子 … Q5=高因子（样本不足则跳过分层）
        if len(pairs) < n_quantiles:
            continue
        pairs_sorted = sorted(pairs, key=lambda p: p[0])
        m = len(pairs_sorted)
        for q in range(n_quantiles):
            lo = m * q // n_quantiles
            hi = m * (q + 1) // n_quantiles
            bucket = pairs_sorted[lo:hi]
            if not bucket:
                continue
            q_daily[q].append(sum(p[1] for p in bucket) / len(bucket))

    ic_mean = sum(daily_ics) / len(daily_ics) if daily_ics else None
    if daily_ics and len(daily_ics) > 1:
        mu = ic_mean or 0.0
        var = sum((x - mu) ** 2 for x in daily_ics) / (len(daily_ics) - 1)
        ic_std = var**0.5
        icir = (ic_mean / ic_std) if ic_std > 1e-12 else None
    else:
        icir = None
    win_rate = (
        sum(1 for x in daily_ics if x > 0) / len(daily_ics) if daily_ics else None
    )

    # 各层累积收益与年化（按交易日 244）
    layer_stats = []
    trading_days_year = 244.0
    for q, series in enumerate(q_daily, start=1):
        if not series:
            layer_stats.append(
                {
                    "quantile": q,
                    "days": 0,
                    "cum_return": None,
                    "ann_return": None,
                }
            )
            continue
        nav = 1.0
        for r in series:
            nav *= 1.0 + r
        cum = nav - 1.0
        n = len(series)
        ann = nav ** (trading_days_year / n) - 1.0 if n > 0 and nav > 0 else None
        layer_stats.append(
            {
                "quantile": q,
                "days": n,
                "cum_return": cum,
                "ann_return": ann,
            }
        )

    q1_cum = layer_stats[0]["cum_return"] if layer_stats else None
    q5_cum = layer_stats[-1]["cum_return"] if layer_stats else None
    long_short = None
    if q1_cum is not None and q5_cum is not None:
        long_short = q5_cum - q1_cum

    return {
        "ic_mean": ic_mean,
        "icir": icir,
        "ic_win_rate": win_rate,
        "ic_days": len(daily_ics),
        "layers": layer_stats,
        "long_short_q5_q1": long_short,
    }


def format_eval_report(factor_code: str, report: dict[str, Any]) -> str:
    lines = [
        f"factor={factor_code}",
        f"IC_mean={report.get('ic_mean')} ICIR={report.get('icir')} "
        f"win={report.get('ic_win_rate')} days={report.get('ic_days')}",
        f"long_short_Q5-Q1={report.get('long_short_q5_q1')}",
        "quantile | days | cum_ret | ann_ret",
    ]
    for layer in report.get("layers") or []:
        lines.append(
            f"Q{layer['quantile']} | {layer['days']} | "
            f"{layer['cum_return']} | {layer['ann_return']}"
        )
    return "\n".join(lines)
