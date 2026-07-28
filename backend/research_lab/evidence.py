from __future__ import annotations

"""研究证据包：OOS 切分、软/硬门槛与可打印结论（纯函数）。"""

import hashlib
import json
from datetime import date, timedelta
from typing import Any


# 证据包默认「值得继续研究」软门槛（非晋升 LIVE 硬门）
DEFAULT_SOFT_GATES: dict[str, Any] = {
    "min_ic_mean": 0.0,
    "min_ic_days": 20,
    "min_icir": 0.0,
    "require_positive_long_short": False,
}

# 证据冻结硬门槛（OOS 稳定性；可在长窗数据上收紧）
DEFAULT_HARD_OOS_GATES: dict[str, Any] = {
    "min_fold_count": 2,
    "min_positive_ic_fold_ratio": 0.5,
    "min_ic_mean_avg": 0.0,
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


def walk_forward_windows(
    start: str,
    end: str,
    *,
    train_days: int = 60,
    test_days: int = 20,
    step_days: int | None = None,
) -> list[tuple[str, str, str, str, str]]:
    """
    日历日 walk-forward。
    返回 [(label, train_start, train_end, test_start, test_end), ...]。
    OOS 评估只用 test 窗；train 写入元数据供审计。
    """
    d0 = date.fromisoformat(start[:10])
    d1 = date.fromisoformat(end[:10])
    train = max(1, int(train_days))
    test = max(1, int(test_days))
    step = max(1, int(step_days if step_days is not None else test))
    if d1 < d0:
        return []
    out: list[tuple[str, str, str, str, str]] = []
    # 首折：train 从 d0 起
    train_start = d0
    i = 0
    while True:
        train_end = train_start + timedelta(days=train - 1)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test - 1)
        if test_end > d1:
            break
        if train_start > d1:
            break
        label = f"wf{i:02d}_{test_start.isoformat()}_{test_end.isoformat()}"
        out.append(
            (
                label,
                train_start.isoformat(),
                train_end.isoformat(),
                test_start.isoformat(),
                test_end.isoformat(),
            )
        )
        i += 1
        train_start = train_start + timedelta(days=step)
    return out


def oos_eval_windows(
    start: str,
    end: str,
    *,
    split_mode: str = "year",
    train_days: int = 60,
    test_days: int = 20,
    step_days: int | None = None,
) -> list[tuple[str, str, str]]:
    """统一为 [(label, eval_start, eval_end), ...] 供 IC 切片。"""
    mode = (split_mode or "year").strip().lower()
    if mode in ("", "none", "off"):
        return []
    if mode == "year":
        return year_windows(start, end)
    if mode in ("walk_forward", "wf"):
        folds = walk_forward_windows(
            start,
            end,
            train_days=train_days,
            test_days=test_days,
            step_days=step_days,
        )
        return [(lab, t0, t1) for lab, _a, _b, t0, t1 in folds]
    return year_windows(start, end)


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


def summarize_oos(by_fold: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """OOS 折 IC 稳定性摘要（年切或 walk-forward 共用）。"""
    folds = sorted(by_fold.keys())
    ic_means: list[float] = []
    pos = 0
    for y in folds:
        rep = by_fold[y].get("report") or {}
        ic = rep.get("ic_mean")
        if ic is None:
            continue
        ic_means.append(float(ic))
        if float(ic) > 0:
            pos += 1
    n = len(ic_means)
    return {
        "folds": folds,
        "years": folds,  # 兼容旧字段名
        "fold_count": n,
        "year_count": n,
        "ic_mean_avg": (sum(ic_means) / n) if n else None,
        "positive_ic_fold_ratio": (pos / n) if n else None,
        "positive_ic_year_ratio": (pos / n) if n else None,
        "ic_mean_min": min(ic_means) if ic_means else None,
        "ic_mean_max": max(ic_means) if ic_means else None,
    }


def hard_oos_verdict(
    oos_summary: dict[str, Any] | None,
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """单因子 OOS 硬门槛（冻结用）。"""
    g = {**DEFAULT_HARD_OOS_GATES, **(gates or {})}
    s = oos_summary or {}
    fails: list[str] = []
    fold_count = int(s.get("fold_count") or s.get("year_count") or 0)
    if fold_count < int(g["min_fold_count"]):
        fails.append("fold_count")
    ratio = s.get("positive_ic_fold_ratio")
    if ratio is None:
        ratio = s.get("positive_ic_year_ratio")
    if ratio is None:
        fails.append("missing_pos_ratio")
    elif float(ratio) < float(g["min_positive_ic_fold_ratio"]):
        fails.append("positive_ic_fold_ratio")
    avg = s.get("ic_mean_avg")
    if avg is None:
        fails.append("missing_ic_mean_avg")
    elif float(avg) < float(g["min_ic_mean_avg"]):
        fails.append("ic_mean_avg")
    return {"passed": len(fails) == 0, "failing": fails, "gates": g}


def pack_freeze_eligibility(
    pack: dict[str, Any],
    hard_gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    包级冻结资格：至少 1 个 committed 因子同时 soft pass + hard OOS pass。
    """
    factors = pack.get("factors") or {}
    eligible: list[str] = []
    detail: dict[str, Any] = {}
    for code, row in factors.items():
        if not isinstance(row, dict) or row.get("status") != "committed":
            continue
        soft = row.get("verdict") or soft_verdict(row.get("report"))
        oos = (row.get("oos") or {}).get("summary")
        hard = hard_oos_verdict(oos, hard_gates)
        detail[code] = {"soft": soft, "hard_oos": hard}
        if soft.get("passed") and hard.get("passed"):
            eligible.append(code)
    return {
        "eligible": bool(eligible),
        "eligible_factors": eligible,
        "detail": detail,
        "split_mode": pack.get("split_mode") or ("year" if pack.get("year_split") else "none"),
    }


def artifact_hash(pack: dict[str, Any]) -> str:
    """对证据包关键字段做稳定哈希，供冻结审计。"""
    slim: dict[str, Any] = {
        "universe_code": pack.get("universe_code"),
        "start": pack.get("start"),
        "end": pack.get("end"),
        "factor_type": pack.get("factor_type"),
        "split_mode": pack.get("split_mode")
        or ("year" if pack.get("year_split") else "none"),
        "walk_forward": pack.get("walk_forward"),
        "factors": {},
    }
    for code, row in (pack.get("factors") or {}).items():
        if not isinstance(row, dict):
            continue
        slim["factors"][code] = {
            "status": row.get("status"),
            "report": row.get("report"),
            "verdict": row.get("verdict"),
            "oos_summary": (row.get("oos") or {}).get("summary"),
            "backtest": {
                k: (row.get("backtest") or {}).get(k)
                for k in (
                    "status",
                    "run_id",
                    "total_return",
                    "max_drawdown",
                    "trade_count",
                )
            }
            if row.get("backtest")
            else None,
        }
    blob = json.dumps(slim, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def format_evidence_pack(pack: dict[str, Any]) -> str:
    split = pack.get("split_mode") or ("year" if pack.get("year_split") else "none")
    lines = [
        f"evidence universe={pack.get('universe_code')} "
        f"{pack.get('start')}→{pack.get('end')}",
        f"factors={len(pack.get('factors') or {})} "
        f"split_mode={split} "
        f"with_backtest={bool(pack.get('with_backtest'))}",
        "",
        "factor | IC_mean | ICIR | days | LS_Q5-Q1 | soft | hard_oos | note",
    ]
    for code, row in (pack.get("factors") or {}).items():
        rep = row.get("report") or {}
        verd = row.get("verdict") or {}
        hard = row.get("hard_oos") or {}
        note = ",".join(verd.get("failing") or []) or "-"
        soft = "PASS" if verd.get("passed") else "FAIL"
        hard_s = (
            "PASS"
            if hard.get("passed")
            else ("FAIL" if hard else "-")
        )
        lines.append(
            f"{code} | {rep.get('ic_mean')} | {rep.get('icir')} | "
            f"{rep.get('ic_days')} | {rep.get('long_short_q5_q1')} | "
            f"{soft} | {hard_s} | {note}"
        )
        oos = row.get("oos") or {}
        if oos:
            s = oos.get("summary") or {}
            lines.append(
                f"  oos folds={s.get('fold_count', s.get('year_count'))} "
                f"avg_ic={s.get('ic_mean_avg')} "
                f"pos_fold_ratio={s.get('positive_ic_fold_ratio', s.get('positive_ic_year_ratio'))}"
            )
        bt = row.get("backtest")
        if bt:
            lines.append(
                f"  backtest status={bt.get('status')} run={bt.get('run_id')} "
                f"ret={bt.get('total_return')} mdd={bt.get('max_drawdown')} "
                f"trades={bt.get('trade_count')}"
            )
    freeze = pack.get("freeze_eligibility")
    if freeze:
        lines.append(
            f"freeze_eligible={freeze.get('eligible')} "
            f"factors={freeze.get('eligible_factors')}"
        )
    return "\n".join(lines)
