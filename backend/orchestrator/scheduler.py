from __future__ import annotations

"""最小日更编排：daily → … → execution → ledger → ops 告警。"""

import logging
import sys
import time
import uuid
from argparse import Namespace
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable

from shared.db import get_conn

logger = logging.getLogger(__name__)


def _main_mod():
    """兼容 `python main.py`（__main__）与 `import main`。"""
    m = sys.modules.get("__main__")
    if m is not None and hasattr(m, "cmd_daily"):
        return m
    import main as m  # noqa: WPS433

    return m


@dataclass
class StepResult:
    name: str
    status: str  # ok / failed / skipped
    exit_code: int = 0
    ref_ids: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class ScheduleResult:
    job_id: str
    as_of: str
    status: str  # committed / degraded / failed / skipped
    steps: list[StepResult] = field(default_factory=list)
    message: str = ""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_open_day(as_of: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT is_open FROM raw_trade_calendar
            WHERE trade_date=? AND is_open=1
            LIMIT 1
            """,
            (as_of[:10],),
        ).fetchone()
    return bool(row)


def run_once(
    *,
    as_of: str | None = None,
    universe: str = "TOP100",
    factor_type: str = "qfq",
    force: bool = False,
    job_id: str | None = None,
) -> ScheduleResult:
    """
    跑一轮日更。非开市日快速跳过（除非 force）。
    CORE（daily）失败则中止后续；ALPHA 失败记录并继续。
    """
    day = (as_of or date.today().isoformat())[:10]
    jid = job_id or f"sched_{uuid.uuid4().hex}"
    started = _utcnow()
    result = ScheduleResult(job_id=jid, as_of=day, status="committed")

    if not force and not is_open_day(day):
        result.status = "skipped"
        result.message = f"{day} 非开市日"
        print(f"status=skipped job_id={jid} message={result.message}")
        return result

    print(f"schedule start job_id={jid} as_of={day} universe={universe}")

    main = _main_mod()

    # --- 1. CORE daily ---
    daily_ns = Namespace(
        as_of=day,
        universe=universe,
        index=[],
        factor_type=factor_type,
        with_alpha=False,
        force=force,
        job_id=jid,
    )
    code = int(main.cmd_daily(daily_ns))
    step = StepResult(
        name="daily",
        status="ok" if code == 0 else "failed",
        exit_code=code,
        ref_ids=[jid],
    )
    result.steps.append(step)
    if code != 0:
        result.status = "failed"
        result.message = "CORE daily failed; abort round"
        _finalize_alerts(
            jid, day, started, schedule_status="failed", message=result.message
        )
        print(f"status=failed job_id={jid} message={result.message}")
        return result

    # --- 2. security_master 快照 ---
    sm_ns = Namespace(
        universe=None,
        p0=True,
        as_of=day,
        industry_standard="SW2021",
        preferred_source="akshare",
        index_symbol="000300",
        strict_open_day=False,
        job_id=jid,
    )
    _safe_call(lambda: int(main.cmd_security_master(sm_ns)), "security_master", result)
    sm_failed = any(
        s.name == "security_master" and s.status == "failed" for s in result.steps
    )

    # --- 3. ALPHA 增量：news_official / news_policy / valuation ---
    _run_alpha_incremental(day, universe, jid, result)

    # --- 4. ALPHA DQ（不进 gate）---
    dq_ns = Namespace(
        scope="ALPHA",
        start=day,
        end=day,
        symbol=[],
        universe=universe,
        universe_as_of=day,
        index=[],
        factor_type=factor_type,
        job_id=jid,
    )
    _safe_call(lambda: int(main.cmd_data_quality(dq_ns)), "alpha_dq", result)

    trading_names = (
        "factor_refresh",
        "signal_live",
        "portfolio_live",
        "risk_review",
        "execution_paper",
        "ledger_post",
    )
    if sm_failed:
        # Universe 陈旧时禁止跑交易链
        for name in trading_names:
            result.steps.append(
                StepResult(
                    name=name,
                    status="skipped",
                    message="skipped: security_master failed",
                )
            )
        print("trading steps skipped due to security_master failure")
        factor_failed = False
    else:
        # --- 4b. LIVE 因子当日刷新（signal 前必须）---
        factor_failed = not _refresh_live_factors(day, jid, result)
        if factor_failed:
            for name in trading_names:
                if name == "factor_refresh":
                    continue
                result.steps.append(
                    StepResult(
                        name=name,
                        status="skipped",
                        message="skipped: factor_refresh failed",
                    )
                )
            print("trading steps skipped due to factor_refresh failure")
        else:
            # --- 5. 生产信号（仅 LIVE）---
            sg_ns = Namespace(
                signal_action="run",
                version=None,
                live=True,
                paper=False,
                start=day,
                end=day,
                as_of=day,
                no_dq_check=False,
                job_id=jid,
            )
            sg_code = _safe_call(
                lambda: int(main.cmd_signal(sg_ns)), "signal_live", result
            )
            signal_failed = sg_code is None or sg_code != 0
            # signal skipped（非调仓）也是 exit 0；仅 failed 短路
            if signal_failed:
                for name in (
                    "portfolio_live",
                    "risk_review",
                    "execution_paper",
                    "ledger_post",
                ):
                    result.steps.append(
                        StepResult(
                            name=name,
                            status="skipped",
                            message="skipped: signal_live failed",
                        )
                    )
                print("trading steps skipped due to signal_live failure")
            else:
                # --- 6. 组合草稿（仅 LIVE；非调仓日 hold skipped）---
                pf_ns = Namespace(
                    portfolio_action="build",
                    version=None,
                    live=True,
                    paper=False,
                    as_of=day,
                    nav=1_000_000.0,
                    account="paper_default",
                    cost_version="v1_ashare_default",
                    signal_batch=None,
                    job_id=jid,
                    fixed_nav=False,
                    force=False,
                )
                _safe_call(
                    lambda: int(main.cmd_portfolio(pf_ns)), "portfolio_live", result
                )

                # --- 7. 风控审核 draft ---
                rk_ns = Namespace(
                    risk_action="review",
                    portfolio=None,
                    drafts=True,
                    as_of=day,
                    account="paper_default",
                    limits_version="v1_default",
                    force=False,
                    actor="schedule",
                    job_id=jid,
                )
                _safe_call(lambda: int(main.cmd_risk(rk_ns)), "risk_review", result)

                # --- 8. 纸面执行 approved（CLI 内每单立即过账）---
                ex_ns = Namespace(
                    execution_action="run",
                    portfolio=None,
                    approved=True,
                    as_of=day,
                    account="paper_default",
                    cost_version="v1_ashare_default",
                    force=False,
                    job_id=jid,
                )
                _safe_call(
                    lambda: int(main.cmd_execution(ex_ns)), "execution_paper", result
                )

                # --- 9. 账本过账（兜底未过账）---
                ld_ns = Namespace(
                    ledger_action="post",
                    execution=None,
                    unposted=True,
                    account="paper_default",
                    force=False,
                    limit=50,
                    job_id=jid,
                )
                _safe_call(lambda: int(main.cmd_ledger(ld_ns)), "ledger_post", result)

    # --- 10. 告警汇总 ---
    failed_coreish = any(
        s.name == "daily" and s.status == "failed" for s in result.steps
    )
    trading_set = set(trading_names)
    trading_fails = sum(
        1 for s in result.steps if s.name in trading_set and s.status == "failed"
    )
    trading_skipped_gate = sm_failed or factor_failed
    alpha_fails = sum(
        1
        for s in result.steps
        if s.name not in ({"daily", "security_master"} | trading_set)
        and s.status == "failed"
    )
    if failed_coreish:
        result.status = "failed"
    elif trading_fails or trading_skipped_gate:
        result.status = "degraded"
        parts: list[str] = []
        if sm_failed:
            parts.append("trading_skipped=security_master")
        if factor_failed:
            parts.append("trading_skipped=factor_refresh")
        if trading_fails:
            parts.append(f"trading_fails={trading_fails}")
        if alpha_fails:
            parts.append(f"alpha_fails={alpha_fails}")
        result.message = "; ".join(parts) + " (CORE ok)"
    elif alpha_fails:
        result.status = "committed"
        result.message = f"alpha_fails={alpha_fails} (CORE ok)"
    else:
        result.status = "committed"

    _finalize_alerts(jid, day, started, schedule_status=result.status, message=result.message)

    print(
        f"status={result.status} job_id={jid} as_of={day} "
        f"steps={len(result.steps)} message={result.message or '-'}"
    )
    return result


def _refresh_live_factors(day: str, job_id: str, result: ScheduleResult) -> bool:
    """
    按 LIVE 策略的 (factor_code, universe, factor_type) 刷新 research_factor_value。
    无 LIVE → ok；任一刷新失败 → False（跳过交易链）。
    """
    import json

    from research_lab.models import FACTOR_CODES, ResearchRequest
    from research_lab.service import ResearchService

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strategy_version, params_json
            FROM strategy_version
            WHERE status='LIVE'
            """
        ).fetchall()

    specs: dict[tuple[str, str, str], str] = {}
    for row in rows:
        try:
            params = json.loads(str(row["params_json"] or "{}"))
        except json.JSONDecodeError:
            params = {}
        fc = str(params.get("factor_code") or "").strip()
        if not fc:
            continue
        uc = str(params.get("universe_code") or "TOP100")
        ft = str(params.get("factor_type") or "qfq")
        specs[(fc, uc, ft)] = str(row["strategy_version"])

    if not specs:
        result.steps.append(
            StepResult(
                name="factor_refresh",
                status="ok",
                message="no LIVE strategies",
            )
        )
        return True

    svc = ResearchService()
    failed: list[str] = []
    ok_n = 0
    for (fc, uc, ft), sv in specs.items():
        if fc not in FACTOR_CODES:
            failed.append(f"{fc}:unsupported")
            continue
        try:
            res = svc.run(
                ResearchRequest(
                    factor_code=fc,  # type: ignore[arg-type]
                    start=day,
                    end=day,
                    universe_code=uc,
                    factor_type=ft,
                    require_dq=True,
                    job_id=job_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("factor_refresh failed factor=%s", fc)
            failed.append(f"{fc}/{uc}:{exc}")
            continue
        if res.status != "committed":
            failed.append(f"{fc}/{uc}:{res.message or res.status}")
        else:
            ok_n += 1
            logger.info(
                "factor_refresh ok factor=%s universe=%s rows=%s strategy=%s",
                fc,
                uc,
                res.row_count,
                sv,
            )

    if failed:
        result.steps.append(
            StepResult(
                name="factor_refresh",
                status="failed",
                exit_code=2,
                message="; ".join(failed),
            )
        )
        return False

    result.steps.append(
        StepResult(
            name="factor_refresh",
            status="ok",
            message=f"refreshed={ok_n}",
        )
    )
    return True


def _safe_call(
    fn: Callable[[], int], name: str, result: ScheduleResult
) -> int | None:
    try:
        code = fn()
    except Exception as exc:  # noqa: BLE001
        logger.exception("schedule step %s failed", name)
        result.steps.append(
            StepResult(name=name, status="failed", exit_code=2, message=str(exc))
        )
        return None
    result.steps.append(
        StepResult(
            name=name,
            status="ok" if code == 0 else "failed",
            exit_code=code,
        )
    )
    return code


def _run_alpha_incremental(
    day: str, universe: str, job_id: str, result: ScheduleResult
) -> None:
    from data_ingest.alpha_fundamental.models import FetchRequest as FundReq
    from data_ingest.alpha_fundamental.service import FundamentalIngestService
    from data_ingest.alpha_fundamental.sources import get_source as get_fund_source
    from data_ingest.alpha_news_monitor.models import FetchRequest as NewsReq
    from data_ingest.alpha_news_monitor.service import NewsIngestService
    from data_ingest.alpha_news_monitor.sources import get_source as get_news_source
    from shared.ingest_batching import resolve_symbols_from_args

    try:
        _, symbols = resolve_symbols_from_args(
            universe=universe, symbols=[], as_of=day
        )
    except ValueError as exc:
        result.steps.append(
            StepResult(name="alpha_resolve", status="failed", message=str(exc))
        )
        return

    news = NewsIngestService(source=get_news_source("akshare"))
    for kind in ("news_official", "news_policy"):
        try:
            r = news.run(NewsReq(kind=kind, job_id=job_id))  # type: ignore[arg-type]
            result.steps.append(
                StepResult(
                    name=kind,
                    status="ok" if r.status == "committed" else "failed",
                    ref_ids=[r.batch_id],
                    message=r.message,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s failed", kind)
            result.steps.append(
                StepResult(name=kind, status="failed", message=str(exc))
            )

    try:
        fund = FundamentalIngestService(source=get_fund_source("akshare"))
        r = fund.run(
            FundReq(
                kind="valuation",
                start=day,
                end=day,
                symbols=symbols,
                job_id=job_id,
            )
        )
        result.steps.append(
            StepResult(
                name="valuation",
                status="ok" if r.status == "committed" else "failed",
                ref_ids=[getattr(r, "batch_id", "") or ""],
                message=getattr(r, "message", "") or "",
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("valuation failed")
        result.steps.append(
            StepResult(name="valuation", status="failed", message=str(exc))
        )

    # 个股资金：供 FLOW_NET_5；分块、单 chunk 失败不阻断
    try:
        from data_ingest.alpha_flow.models import FetchRequest as FlowReq
        from data_ingest.alpha_flow.service import FlowIngestService
        from data_ingest.alpha_flow.sources import get_source as get_flow_source

        flow = FlowIngestService(source=get_flow_source("akshare"))
        chunk_results = flow.run_stock_flow_chunked(
            FlowReq(
                kind="stock_flow",
                start=day,
                end=day,
                symbols=symbols,
                job_id=job_id,
            ),
            chunk_size=20,
        )
        ok_n = sum(1 for x in chunk_results if x.status == "committed")
        fail_n = len(chunk_results) - ok_n
        fetched = sum(int(x.fetched or 0) for x in chunk_results)
        result.steps.append(
            StepResult(
                name="stock_flow",
                status="ok" if fail_n == 0 and chunk_results else "failed",
                ref_ids=[x.batch_id for x in chunk_results if x.batch_id],
                message=f"chunks_ok={ok_n}/{len(chunk_results)};fetched={fetched}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("stock_flow failed")
        result.steps.append(
            StepResult(name="stock_flow", status="failed", message=str(exc))
        )


def _finalize_alerts(
    job_id: str,
    as_of: str,
    since: str,
    *,
    schedule_status: str = "committed",
    message: str = "",
) -> None:
    try:
        from ops_monitor.notify import notify_round

        notify_round(
            job_id=job_id,
            as_of=as_of,
            since=since,
            schedule_status=schedule_status,
            schedule_message=message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("notify_round failed: %s", exc)
        print(f"ops_notify failed: {exc}")


def run_at_loop(
    *,
    at_hhmm: str,
    universe: str = "TOP100",
    factor_type: str = "qfq",
    force: bool = False,
) -> None:
    """进程内定时：每天 HH:MM 跑一轮（stdlib）。"""
    parts = at_hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError("--at 需要 HH:MM")
    hh, mm = int(parts[0]), int(parts[1])
    print(f"schedule loop armed at={hh:02d}:{mm:02d} universe={universe}")
    last_run_day: str | None = None
    while True:
        now = datetime.now().astimezone()
        day = now.date().isoformat()
        if now.hour == hh and now.minute == mm and last_run_day != day:
            run_once(
                as_of=day,
                universe=universe,
                factor_type=factor_type,
                force=force,
            )
            last_run_day = day
            time.sleep(60)
        else:
            time.sleep(15)
