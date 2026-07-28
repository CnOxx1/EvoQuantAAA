from __future__ import annotations

"""研究证据包：年切 OOS 汇总与可打印结论（纯函数）。"""

from datetime import date
from typing import Any


# 证据包默认「值得继续研究」软门槛（非晋升 LIVE 硬门）
DEFAULT_SOFT_GATES: dict[str, Any] = {
    "min_ic_mean": 0.0,
    "min_ic_days": 20,
    "min_icir": 0.0,
    "require_positive_long_short": False,
}


def year_windows(start: str, end: str) -> list[tuple[str, str, str]]:
    """返回 [(year_label, win_start, win_end), ...] 按自然年切分。"""
    d0 = date.fromisoformat(start[:10])
    d1 = date.fromisoformat(end[:10])
    if d1 < d0:
        return []
    out: list[tuple[str, str, str]] = []
    y = d0.year
    while y <= d1.year:
        ys = date(y, 1, 1)
        ye = date(y, 12, 31)
        w0 = max(d0, ys)
        w1 = min(d1, ye)
        if w0 <= w1:
            out.append((str(y), w0.isoformat(), w1.isoformat()))
        y += 1
    return out


def soft_verdict(report: dict[str, Any] | None, gates: dict[str, Any] | None = None) -> dict[str, Any]:
    """对单因子全样本报告给 soft pass/fail（研究用，非 registry 硬门）。"""
    g = {**DEFAULT_SOFT_GATES, **(gates or {})}
    r = report or {}
    fails: list[str] = []
    ic_mean = r.get("ic_mean")
    icir = r.get("icir")
    ic_days = int(r.get("ic_days") or 0)
    ls = r.get("long_short_q5_q1")

    if ic_mean is None:
        fails.append("missing_ic_mean")
    elif float(ic_mean) < float(g["min_ic_mean"]):
        fails.append("ic_mean")

    if ic_days < int(g["min_ic_days"]):
        fails.append("ic_days")

    min_icir = g.get("min_icir")
    if min_icir is not None and icir is not None and float(icir) < float(min_icir):
        fails.append("icir")

    if g.get("require_positive_long_short") and (ls is None or float(ls) <= 0):
        fails.append("long_short")

    return {
        "passed": len(fails) == 0,
        "failing": fails,
        "gates": g,
    }


def summarize_oos(by_year: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """年切 IC 稳定性摘要。"""
    years = sorted(by_year.keys())
    ic_means: list[float] = []
    pos = 0
    for y in years:
        rep = by_year[y].get("report") or {}
        ic = rep.get("ic_mean")
        if ic is None:
            continue
        ic_means.append(float(ic))
        if float(ic) > 0:
            pos += 1
    n = len(ic_means)
    return {
        "years": years,
        "year_count": n,
        "ic_mean_avg": (sum(ic_means) / n) if n else None,
        "positive_ic_year_ratio": (pos / n) if n else None,
        "ic_mean_min": min(ic_means) if ic_means else None,
        "ic_mean_max": max(ic_means) if ic_means else None,
    }


def format_evidence_pack(pack: dict[str, Any]) -> str:
    lines = [
        f"evidence universe={pack.get('universe_code')} "
        f"{pack.get('start')}→{pack.get('end')}",
        f"factors={len(pack.get('factors') or {})} "
        f"year_split={bool(pack.get('year_split'))} "
        f"with_backtest={bool(pack.get('with_backtest'))}",
        "",
        "factor | IC_mean | ICIR | days | LS_Q5-Q1 | soft | note",
    ]
    for code, row in (pack.get("factors") or {}).items():
        rep = row.get("report") or {}
        verd = row.get("verdict") or {}
        note = ",".join(verd.get("failing") or []) or "-"
        soft = "PASS" if verd.get("passed") else "FAIL"
        lines.append(
            f"{code} | {rep.get('ic_mean')} | {rep.get('icir')} | "
            f"{rep.get('ic_days')} | {rep.get('long_short_q5_q1')} | "
            f"{soft} | {note}"
        )
        oos = row.get("oos") or {}
        if oos:
            s = oos.get("summary") or {}
            lines.append(
                f"  oos years={s.get('year_count')} "
                f"avg_ic={s.get('ic_mean_avg')} "
                f"pos_year_ratio={s.get('positive_ic_year_ratio')}"
            )
        bt = row.get("backtest")
        if bt:
            lines.append(
                f"  backtest status={bt.get('status')} run={bt.get('run_id')} "
                f"ret={bt.get('total_return')} mdd={bt.get('max_drawdown')} "
                f"trades={bt.get('trade_count')}"
            )
    return "\n".join(lines)
