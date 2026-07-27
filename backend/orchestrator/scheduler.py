from __future__ import annotations

"""最小日更编排：daily → security_master → ALPHA → ALPHA DQ → ops 告警。"""

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
    status: str  # committed / failed / skipped
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
        _finalize_alerts(jid, day, started)
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

    # --- 5. 告警汇总 ---
    _finalize_alerts(jid, day, started)

    failed_coreish = any(
        s.name == "daily" and s.status == "failed" for s in result.steps
    )
    alpha_fails = sum(
        1 for s in result.steps if s.name != "daily" and s.status == "failed"
    )
    if failed_coreish:
        result.status = "failed"
    elif alpha_fails:
        result.status = "committed"
        result.message = f"alpha_fails={alpha_fails} (CORE ok)"
    else:
        result.status = "committed"

    print(
        f"status={result.status} job_id={jid} as_of={day} "
        f"steps={len(result.steps)} message={result.message or '-'}"
    )
    return result


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


def _finalize_alerts(job_id: str, as_of: str, since: str) -> None:
    try:
        from ops_monitor.notify import notify_round

        notify_round(job_id=job_id, as_of=as_of, since=since)
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
