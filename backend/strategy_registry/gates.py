from __future__ import annotations

"""晋升质量门：纯函数评估（无 DB），供 service / selfcheck / pytest 复用。"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any


DEFAULT_GATE_VERSION = "v1_default"

# 触发质量门的目标状态（RETIRED / 降级 LIVE→PAPER 不评估）
GATED_STATUSES: frozenset[str] = frozenset({"BACKTESTED", "PAPER", "LIVE"})


@dataclass
class GateCheck:
    name: str
    ok: bool
    actual: Any
    threshold: Any
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "actual": self.actual,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class GateEvaluation:
    passed: bool
    gate_version: str
    to_status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    checks: list[GateCheck] = field(default_factory=list)
    message: str = ""

    def failing_names(self) -> list[str]:
        return [c.name for c in self.checks if not c.ok]


def parse_thresholds(raw: str | dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        data = raw
    else:
        data = json.loads(str(raw))
    out: dict[str, dict[str, Any]] = {}
    for key, val in data.items():
        if isinstance(val, dict):
            out[str(key).upper()] = dict(val)
    return out


def calendar_days(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        d0 = date.fromisoformat(str(start)[:10])
        d1 = date.fromisoformat(str(end)[:10])
    except ValueError:
        return None
    return (d1 - d0).days + 1


def extract_ic_report(meta: Any) -> dict[str, Any]:
    """从 research_run.meta_json 取出 evaluate 报告。"""
    if meta is None:
        return {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return {}
    if not isinstance(meta, dict):
        return {}
    report = meta.get("report")
    if isinstance(report, dict):
        return report
    return {}


def evaluate_promotion_gates(
    *,
    to_status: str,
    thresholds_by_status: dict[str, dict[str, Any]],
    gate_version: str,
    backtest: dict[str, Any] | None,
    research_meta: Any = None,
    research_run_id: str | None = None,
) -> GateEvaluation:
    """
    评估晋升门槛。

    backtest 期望字段：status, start_date, end_date, total_return, max_drawdown, trade_count
    max_drawdown 为非负比例（引擎口径：峰值回撤幅度）。
    """
    status = str(to_status).upper()
    if status not in GATED_STATUSES:
        return GateEvaluation(
            passed=True,
            gate_version=gate_version,
            to_status=status,
            message="non-gated status",
        )

    rules = thresholds_by_status.get(status)
    if not rules:
        return GateEvaluation(
            passed=False,
            gate_version=gate_version,
            to_status=status,
            message=f"gate params 缺少 {status} 阈值",
            checks=[
                GateCheck(
                    name="thresholds_present",
                    ok=False,
                    actual=None,
                    threshold=status,
                    message=f"thresholds_json 无 {status}",
                )
            ],
        )

    checks: list[GateCheck] = []
    metrics: dict[str, Any] = {}

    if not backtest:
        checks.append(
            GateCheck(
                name="backtest_present",
                ok=False,
                actual=None,
                threshold="committed backtest_run",
                message="缺少 committed backtest_run",
            )
        )
        return GateEvaluation(
            passed=False,
            gate_version=gate_version,
            to_status=status,
            metrics=metrics,
            checks=checks,
            message="缺少 committed backtest_run",
        )

    bt_status = str(backtest.get("status") or "")
    checks.append(
        GateCheck(
            name="backtest_committed",
            ok=bt_status == "committed",
            actual=bt_status,
            threshold="committed",
            message="" if bt_status == "committed" else "backtest 未 committed",
        )
    )

    total_return = backtest.get("total_return")
    max_dd = backtest.get("max_drawdown")
    trade_count = backtest.get("trade_count")
    start = backtest.get("start_date")
    end = backtest.get("end_date")
    days = calendar_days(
        str(start) if start is not None else None,
        str(end) if end is not None else None,
    )

    metrics.update(
        {
            "backtest_run_id": backtest.get("run_id"),
            "total_return": total_return,
            "max_drawdown": max_dd,
            "trade_count": trade_count,
            "start_date": start,
            "end_date": end,
            "calendar_days": days,
            "research_run_id": research_run_id,
        }
    )

    max_dd_lim = float(rules.get("max_drawdown", 1.0))
    dd_ok = max_dd is not None and float(max_dd) <= max_dd_lim
    checks.append(
        GateCheck(
            name="max_drawdown",
            ok=dd_ok,
            actual=max_dd,
            threshold=f"<= {max_dd_lim}",
            message="" if dd_ok else f"max_drawdown={max_dd} 超过上限 {max_dd_lim}",
        )
    )

    min_ret = float(rules.get("min_total_return", -1.0))
    ret_ok = total_return is not None and float(total_return) >= min_ret
    checks.append(
        GateCheck(
            name="min_total_return",
            ok=ret_ok,
            actual=total_return,
            threshold=f">= {min_ret}",
            message="" if ret_ok else f"total_return={total_return} 低于下限 {min_ret}",
        )
    )

    min_days = int(rules.get("min_calendar_days", 1))
    days_ok = days is not None and int(days) >= min_days
    checks.append(
        GateCheck(
            name="min_calendar_days",
            ok=days_ok,
            actual=days,
            threshold=f">= {min_days}",
            message="" if days_ok else f"calendar_days={days} 不足 {min_days}",
        )
    )

    min_trades = int(rules.get("min_trade_count", 1))
    trades_ok = trade_count is not None and int(trade_count) >= min_trades
    checks.append(
        GateCheck(
            name="min_trade_count",
            ok=trades_ok,
            actual=trade_count,
            threshold=f">= {min_trades}",
            message="" if trades_ok else f"trade_count={trade_count} 不足 {min_trades}",
        )
    )

    require_ic = bool(rules.get("require_research_ic", False))
    report = extract_ic_report(research_meta)
    ic_mean = report.get("ic_mean")
    icir = report.get("icir")
    ic_days = report.get("ic_days")
    metrics["ic_mean"] = ic_mean
    metrics["icir"] = icir
    metrics["ic_days"] = ic_days

    if require_ic:
        has_research = bool(research_run_id) and bool(report)
        checks.append(
            GateCheck(
                name="research_ic_present",
                ok=has_research,
                actual={"research_run_id": research_run_id, "has_report": bool(report)},
                threshold="committed research_run with report",
                message="" if has_research else "LIVE 要求关联 research_run 且含 IC 报告",
            )
        )
        if has_research:
            min_ic = rules.get("min_ic_mean")
            if min_ic is not None:
                min_ic_f = float(min_ic)
                ic_ok = ic_mean is not None and float(ic_mean) >= min_ic_f
                checks.append(
                    GateCheck(
                        name="min_ic_mean",
                        ok=ic_ok,
                        actual=ic_mean,
                        threshold=f">= {min_ic_f}",
                        message="" if ic_ok else f"ic_mean={ic_mean} 低于 {min_ic_f}",
                    )
                )
            min_icir = rules.get("min_icir")
            if min_icir is not None:
                min_icir_f = float(min_icir)
                icir_ok = icir is not None and float(icir) >= min_icir_f
                checks.append(
                    GateCheck(
                        name="min_icir",
                        ok=icir_ok,
                        actual=icir,
                        threshold=f">= {min_icir_f}",
                        message="" if icir_ok else f"icir={icir} 低于 {min_icir_f}",
                    )
                )
            min_ic_days = rules.get("min_ic_days")
            if min_ic_days is not None:
                min_ic_days_i = int(min_ic_days)
                ic_days_ok = ic_days is not None and int(ic_days) >= min_ic_days_i
                checks.append(
                    GateCheck(
                        name="min_ic_days",
                        ok=ic_days_ok,
                        actual=ic_days,
                        threshold=f">= {min_ic_days_i}",
                        message=""
                        if ic_days_ok
                        else f"ic_days={ic_days} 不足 {min_ic_days_i}",
                    )
                )
    elif research_run_id and report:
        # 有研究则可选校验（阈值存在才查）
        min_ic = rules.get("min_ic_mean")
        if min_ic is not None and ic_mean is not None:
            min_ic_f = float(min_ic)
            ic_ok = float(ic_mean) >= min_ic_f
            checks.append(
                GateCheck(
                    name="min_ic_mean",
                    ok=ic_ok,
                    actual=ic_mean,
                    threshold=f">= {min_ic_f}",
                    message="" if ic_ok else f"ic_mean={ic_mean} 低于 {min_ic_f}",
                )
            )

    failed = [c for c in checks if not c.ok]
    passed = len(failed) == 0
    msg = ""
    if not passed:
        msg = "质量门未通过: " + "; ".join(
            c.message or c.name for c in failed if c.message or c.name
        )
    return GateEvaluation(
        passed=passed,
        gate_version=gate_version,
        to_status=status,
        metrics=metrics,
        checks=checks,
        message=msg,
    )
