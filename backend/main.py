from __future__ import annotations

"""
后端入口。

示例：
  cd backend
  python main.py migrate
  python main.py core_ref --kind calendar --start 2026-07-01 --end 2026-07-31
  python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
  python main.py core_market --p0 --start 2026-07-21 --end 2026-07-23 --symbol 600000 --symbol 000001
  python main.py security_master --p0 --as-of 2026-07-23
  python main.py core_market --p0 --universe TOP100 --start 2026-07-01 --end 2026-07-23 --skip-existing --chunk-size 10
  python main.py alpha_fundamental --p1 --universe TOP100 --start 2026-07-01 --skip-existing --chunk-size 10
  # 非龙头个股：按需单票拉取，勿对 ALL_LISTED 全市场灌数
  python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600519
  python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 100
  python main.py core_market --kind market_rank --universe TOP100 --start 2026-07-01 --end 2026-07-23 --rank-type VOLUME --rank-type PCT_CHG_UP
  python main.py core_market --kind abnormal_move --start 2026-07-23 --end 2026-07-23
  python main.py alpha_flow --kind dragon_tiger --start 2026-07-01 --end 2026-07-23
  python main.py alpha_flow --kind dragon_tiger_seat --start 2026-07-01 --end 2026-07-23
  python main.py alpha_flow --kind block_trade --start 2026-07-01 --end 2026-07-23
  python main.py core_market --kind suspend --start 2023-01-01 --end 2026-07-23 --chunk-months 1 --skip-existing
  python main.py core_market --kind board_1d --start 2026-07-01 --end 2026-07-23 --board-type INDUSTRY
  python main.py alpha_fundamental --kind valuation --universe TOP100 --start 2026-07-01 --end 2026-07-23 --chunk-size 10
  python main.py alpha_fundamental --kind holder --universe TOP100 --chunk-size 10
  python main.py core_ref --kind restricted_release --start 2026-07-01 --end 2026-07-23
  python main.py daily --universe TOP100 --as-of 2026-07-23
  python main.py alpha_contract --kind win_bid --start 2026-07-01 --end 2026-07-25
  python main.py alpha_announcement --kind ann_by_category --category win_bid --start 2026-07-24 --end 2026-07-24
  python main.py alpha_relation --kind hot_relate --universe TOP100 --end 2026-07-25
"""

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from security_master.models import UNIVERSE_CHOICES

from shared.config import settings  # noqa: E402
from shared.db import apply_migration_file  # noqa: E402
from shared.logging_utils import setup_logging  # noqa: E402


def cmd_migrate(_: argparse.Namespace) -> int:
    mig_dir = BACKEND_ROOT.parent / "database" / "migrations"
    paths = sorted(mig_dir.glob("*.sql"))
    if not paths:
        print(f"未找到迁移: {mig_dir}")
        return 1
    for path in paths:
        apply_migration_file(path)
        print(f"已应用迁移: {path.name}")
    print(f"数据库: {settings.database_url}")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    from backtest.models import BacktestRequest
    from backtest.service import BacktestService

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    try:
        result = BacktestService().run(
            BacktestRequest(
                strategy_code=args.strategy,
                start=args.start,
                end=args.end,
                symbols=symbols,
                universe_code=args.universe,
                factor_type=args.factor_type,
                cost_version=args.cost_version,
                benchmark_index=args.benchmark,
                initial_cash=args.cash,
                require_dq=not args.no_dq_check,
                rebalance_days=int(getattr(args, "rebalance_days", 0) or 0),
                research_factor=getattr(args, "research_factor", None),
                top_n=int(getattr(args, "top_n", 20) or 20),
                job_id=args.job_id,
            )
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} run_id={result.run_id} strategy={result.strategy_code} "
        f"final_nav={result.final_nav:.4f} total_return={result.total_return:.6f} "
        f"benchmark_return={result.benchmark_return:.6f} max_drawdown={result.max_drawdown:.6f} "
        f"trades={result.trade_count}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_research(args: argparse.Namespace) -> int:
    from research_lab.models import FACTOR_CODES, ResearchRequest
    from research_lab.service import ResearchService

    factors = list(FACTOR_CODES) if args.factor == "ALL" else [args.factor]
    exit_code = 0
    for code in factors:
        req = ResearchRequest(
            factor_code=code,  # type: ignore[arg-type]
            start=args.start,
            end=args.end,
            universe_code=args.universe,
            factor_type=args.factor_type,
            require_dq=not args.no_dq_check,
            job_id=args.job_id,
        )
        try:
            if args.evaluate:
                result = ResearchService().evaluate(req)
            else:
                result = ResearchService().run(req)
        except ValueError as exc:
            print(f"status=invalid factor={code} message={exc}")
            exit_code = 2
            continue
        print(
            f"status={result.status} run_id={result.run_id} factor={result.factor_code} "
            f"universe={result.universe_code} rows={result.row_count}"
        )
        if result.message:
            print(result.message)
        if result.status != "committed":
            exit_code = 2
    return exit_code


def cmd_security_master(args: argparse.Namespace) -> int:
    from security_master.models import UniverseBuildRequest
    from security_master.service import SecurityMasterService

    service = SecurityMasterService()
    base = UniverseBuildRequest(
        universe_code=args.universe or "ALL_LISTED",
        as_of_date=args.as_of,
        industry_standard=args.industry_standard,
        preferred_source=args.preferred_source,
        index_symbol=args.index_symbol,
        job_id=args.job_id,
        allow_non_open_day=not args.strict_open_day,
    )
    try:
        if args.p0:
            results = service.build_p0(base)
            ok = True
            for r in results:
                print(
                    f"universe={r.universe_code} status={r.status} "
                    f"snapshot_id={r.universe_snapshot_id} as_of={r.as_of_date} "
                    f"members={r.member_count}"
                )
                if r.message:
                    print(f"message={r.message}")
                ok = ok and r.status == "committed"
            return 0 if ok else 2
        if not args.universe:
            print("status=invalid message=请指定 --universe 或使用 --p0")
            return 2
        result = service.build(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} snapshot_id={result.universe_snapshot_id} "
        f"universe={result.universe_code} as_of={result.as_of_date} "
        f"members={result.member_count}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_data_quality(args: argparse.Namespace) -> int:
    from data_quality.models import DqRequest
    from data_quality.service import DataQualityService
    from shared.ingest_batching import resolve_symbols_from_args

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")
    req = DqRequest(
        scope=args.scope,
        start=args.start,
        end=args.end,
        symbols=symbols,
        index_symbols=indexes,
        factor_type=args.factor_type,
        job_id=args.job_id,
    )
    try:
        if args.scope == "CORE":
            result = DataQualityService().run_core(req)
        elif args.scope == "ALPHA":
            result = DataQualityService().run_alpha(req)
        else:
            print(f"status=invalid message=不支持 scope={args.scope}")
            return 2
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} dq_run_id={result.dq_run_id} scope={result.scope} "
        f"error_fails={result.error_fails} warn_fails={result.warn_fails} "
        f"rules={result.rule_count}"
    )
    if result.message:
        print(f"message={result.message}")
    # ALPHA 仅报告：有告警也不阻断（exit 0）；真正异常才非 0
    if args.scope == "ALPHA":
        return 2 if result.message else 0
    return 0 if result.status == "passed" else 2


def cmd_data_process(args: argparse.Namespace) -> int:
    from data_process.models import ProcessRequest
    from data_process.service import DataProcessService
    from shared.universe_resolve import resolve_universe_symbols

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    if args.universe:
        if not args.start:
            print("status=invalid message=--universe 需要 --start")
            return 2
        sid, uni_symbols = resolve_universe_symbols(
            universe_code=args.universe,
            as_of=args.universe_as_of or args.start,
            as_of_end=args.end,
        )
        if not uni_symbols:
            print(f"status=invalid message=Universe {args.universe} 无成员快照")
            return 2
        print(f"universe={args.universe} snapshot_id={sid} members={len(uni_symbols)}")
        symbols = uni_symbols if not symbols else [s for s in symbols if s in set(uni_symbols)]
    service = DataProcessService()
    base = ProcessRequest(
        kind=args.kind or "equity_1d",
        start=args.start,
        end=args.end,
        symbols=symbols,
        index_symbols=indexes,
        factor_type=args.factor_type,
        preferred_source=args.preferred_source,
        job_id=args.job_id,
    )
    try:
        if args.p0:
            results = service.run_p0(base)
            ok = True
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} process_batch_id={r.process_batch_id} "
                    f"input={r.input_rows} output={r.output_rows} "
                    f"inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
                ok = ok and r.status == "committed"
            return 0 if ok else 2

        if not args.kind:
            print("status=invalid message=请指定 --kind 或使用 --p0")
            return 2
        result = service.run(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} process_batch_id={result.process_batch_id} "
        f"kind={result.kind} input={result.input_rows} output={result.output_rows} "
        f"inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_alpha_announcement(args: argparse.Namespace) -> int:
    from data_ingest.alpha_announcement.models import FetchRequest
    from data_ingest.alpha_announcement.service import AnnouncementIngestService
    from data_ingest.alpha_announcement.sources import get_source

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    categories = [c.strip() for c in (args.category or []) if c.strip()]
    request = FetchRequest(
        kind=args.kind,
        start=args.start,
        end=args.end,
        symbols=symbols or None,
        categories=categories or None,
        page_size=args.page_size,
        max_pages=args.max_pages,
        job_id=args.job_id,
    )
    source = get_source(args.source)
    service = AnnouncementIngestService(
        source=source,
        fallback_mock_on_error=not args.no_fallback,
    )
    try:
        result = service.run(request)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    print(
        f"status={result.status} batch_id={result.batch_id} "
        f"fetched={result.fetched} inserted={result.inserted} "
        f"updated={result.updated} watermark={result.watermark}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_core_ref(args: argparse.Namespace) -> int:
    from data_ingest.core_ref.models import FetchRequest
    from data_ingest.core_ref.service import CoreRefIngestService
    from data_ingest.core_ref.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args

    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    symbols = [s.strip() for s in (getattr(args, "symbol", None) or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.start or args.end,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")
    try:
        source = get_source(args.source)
    except NotImplementedError as exc:
        print(f"status=invalid message={exc}")
        return 2

    if hasattr(source, "share_capital_sh_limit"):
        # 0 → 全量；正整数 → 限流
        limit = None if args.share_sh_limit == 0 else args.share_sh_limit
        source.share_capital_sh_limit = limit

    service = CoreRefIngestService(source=source)
    base = FetchRequest(
        kind=args.kind or "calendar",
        start=args.start,
        end=args.end,
        exchange=args.exchange,
        industry_standard=args.industry_standard,
        index_symbols=indexes,
        symbols=symbols,
        job_id=args.job_id,
    )
    try:
        if args.p0:
            if not (args.start and args.end):
                print("status=invalid message=--p0 需要同时提供 --start 与 --end")
                return 2
            results = service.run_p0(base)
            ok = True
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
                ok = ok and r.status == "committed"
            return 0 if ok else 2

        if not args.kind:
            print("status=invalid message=请指定 --kind 或使用 --p0")
            return 2
        result = service.run(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_core_market(args: argparse.Namespace) -> int:
    from data_ingest.core_market.models import FetchRequest
    from data_ingest.core_market.service import CoreMarketIngestService
    from data_ingest.core_market.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args, should_chunk
    from shared.universe_resolve import (
        symbols_missing_corp_action,
        symbols_missing_equity_bars,
    )

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=args.universe,
            symbols=symbols,
            as_of=args.universe_as_of or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if args.universe:
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")

    kind = args.kind or "equity_1d"
    min_bars = max(1, int(getattr(args, "min_bars", None) or 1))
    if (
        args.skip_existing
        and args.start
        and args.end
        and symbols
        and kind != "market_rank"
    ):
        before = len(symbols)
        if kind == "corp_action" and not args.p0:
            symbols = symbols_missing_corp_action(
                symbols, start=args.start, end=args.end, min_rows=min_bars
            )
            print(
                f"skip_existing: keep {len(symbols)}/{before} "
                f"missing corp_action (min_bars={min_bars})"
            )
        else:
            symbols = symbols_missing_equity_bars(
                symbols, start=args.start, end=args.end, min_rows=min_bars
            )
            print(
                f"skip_existing: keep {len(symbols)}/{before} "
                f"missing equity bars (min_bars={min_bars})"
            )

    source = get_source(args.source)
    service = CoreMarketIngestService(source=source)
    rank_types = [t.strip().upper() for t in (args.rank_type or []) if t.strip()]
    board_types = [t.strip().upper() for t in (getattr(args, "board_type", None) or []) if t.strip()]
    board_names = [t.strip() for t in (getattr(args, "board_name", None) or []) if t.strip()]
    chunk_months = int(getattr(args, "chunk_months", None) or 0)
    base = FetchRequest(
        kind=kind,  # type: ignore[arg-type]
        start=args.start,
        end=args.end,
        symbols=symbols,
        index_symbols=indexes,
        job_id=args.job_id,
        top_n=int(getattr(args, "top_n", None) or 100),
        rank_types=rank_types,
        prefer_spot=bool(getattr(args, "prefer_spot", False)),
        change_types=[t.strip() for t in (args.change_type or []) if t.strip()],
        board_types=board_types,
        board_names=board_names,
    )
    chunking = should_chunk(
        symbols,
        chunked=args.chunked,
        universe=args.universe,
        chunk_size=args.chunk_size,
    )
    date_chunk_kinds = {"suspend", "limit", "market_rank", "abnormal_move", "board_1d"}
    try:
        if args.p0:
            if not (args.start and args.end):
                print("status=invalid message=--p0 需要同时提供 --start 与 --end")
                return 2
            if not symbols and not args.skip_existing:
                print("status=invalid message=--p0 需要 --symbol 或 --universe")
                return 2
            if not symbols and args.skip_existing:
                print("skip_existing: 无需补 equity/adj，仅刷新 suspend/limit/index")
                base.symbols = []
                results = []
                cm = chunk_months or 1
                for mk in ("suspend", "limit"):
                    req = FetchRequest(
                        kind=mk,  # type: ignore[arg-type]
                        start=args.start,
                        end=args.end,
                        symbols=[],
                        index_symbols=indexes or ["000300"],
                        job_id=args.job_id,
                    )
                    results.extend(
                        service.run_range_kind_chunked(
                            req,
                            chunk_months=cm,
                            skip_existing=True,
                        )
                    )
                results.append(
                    service.run(
                        FetchRequest(
                            kind="index_1d",
                            start=args.start,
                            end=args.end,
                            symbols=[],
                            index_symbols=indexes or ["000300"],
                            job_id=args.job_id,
                        )
                    )
                )
            elif chunking:
                results = service.run_p0_chunked(
                    base,
                    chunk_size=args.chunk_size,
                    chunk_months=chunk_months or 1,
                )
            else:
                results = service.run_p0(base)
            committed = sum(1 for r in results if r.status == "committed")
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
            ok = committed > 0 if chunking else all(
                r.status == "committed" for r in results
            )
            print(f"summary committed_batches={committed}/{len(results)}")
            return 0 if ok else 2

        if not args.kind:
            print("status=invalid message=请指定 --kind 或使用 --p0")
            return 2
        if kind in {"equity_1d", "adj_factor", "corp_action"}:
            if not symbols:
                if args.skip_existing:
                    print("skip_existing: 无需补数，退出")
                    return 0
                print("status=invalid message=该 kind 需要 --symbol 或 --universe")
                return 2
            if chunking:
                results = service.run_symbol_kind_chunked(
                    base, chunk_size=args.chunk_size
                )
                committed = sum(1 for r in results if r.status == "committed")
                for r in results:
                    print(
                        f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                        f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                    )
                    if r.message:
                        print(f"message={r.message}")
                print(f"summary committed_batches={committed}/{len(results)}")
                return 0 if committed > 0 else 2
        if kind in date_chunk_kinds and (chunk_months or args.skip_existing):
            results = service.run_range_kind_chunked(
                base,
                chunk_months=chunk_months or 1,
                skip_existing=bool(args.skip_existing),
            )
            if not results:
                print("skip_existing: 无需补数，退出")
                return 0
            committed = sum(1 for r in results if r.status == "committed")
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
            print(f"summary committed_batches={committed}/{len(results)}")
            return 0 if committed > 0 else 2
        result = service.run(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_daily(args: argparse.Namespace) -> int:
    """交易日增量：CORE 行情 + 排名/异动 → process → DQ（ALPHA 可选）。"""
    from datetime import date

    from data_ingest.core_market.models import FetchRequest as MktReq
    from data_ingest.core_market.service import CoreMarketIngestService
    from data_ingest.core_market.sources import get_source as get_mkt_source
    from data_process.models import ProcessRequest
    from data_process.service import DataProcessService
    from data_quality.models import DqRequest
    from data_quality.service import DataQualityService
    from shared.db import get_conn
    from shared.ingest_batching import resolve_symbols_from_args
    from shared.universe_resolve import symbols_missing_equity_bars

    as_of = (args.as_of or date.today().isoformat())[:10]
    universe = args.universe or "TOP100"
    indexes = [s.strip() for s in (args.index or []) if s.strip()] or ["000300"]

    # 交易日守卫
    with get_conn() as conn:
        cal = conn.execute(
            """
            SELECT is_open FROM raw_trade_calendar
            WHERE trade_date=? AND is_open=1
            LIMIT 1
            """,
            (as_of,),
        ).fetchone()
    if not cal and not args.force:
        print(f"status=skipped message={as_of} 非开市日（加 --force 强制）")
        return 0

    try:
        sid, symbols = resolve_symbols_from_args(
            universe=universe,
            symbols=[],
            as_of=as_of,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    print(f"daily as_of={as_of} universe={universe} snapshot_id={sid} members={len(symbols)}")

    mkt = CoreMarketIngestService(source=get_mkt_source("akshare"))
    results = []
    failed = 0

    # equity/adj 增量
    missing = symbols_missing_equity_bars(symbols, start=as_of, end=as_of, min_rows=1)
    print(f"equity missing={len(missing)}/{len(symbols)}")
    if missing:
        for kind in ("equity_1d", "adj_factor"):
            r = mkt.run(
                MktReq(kind=kind, start=as_of, end=as_of, symbols=missing, job_id=args.job_id)  # type: ignore[arg-type]
            )
            results.append(r)
            print(f"kind={r.kind} status={r.status} fetched={r.fetched}")
            if r.status != "committed":
                failed += 1

    for kind in ("suspend", "limit", "index_1d", "market_rank", "abnormal_move"):
        req = MktReq(
            kind=kind,  # type: ignore[arg-type]
            start=as_of,
            end=as_of,
            symbols=[],
            index_symbols=indexes,
            job_id=args.job_id,
            prefer_spot=(kind == "market_rank"),
            top_n=200,
        )
        r = mkt.run(req)
        results.append(r)
        print(f"kind={r.kind} status={r.status} fetched={r.fetched}")
        if r.status != "committed":
            failed += 1

    if args.with_alpha:
        from data_ingest.alpha_fundamental.models import FetchRequest as FundReq
        from data_ingest.alpha_fundamental.service import FundamentalIngestService
        from data_ingest.alpha_fundamental.sources import get_source as get_fund_source
        from data_ingest.alpha_flow.models import FetchRequest as FlowReq
        from data_ingest.alpha_flow.service import FlowIngestService
        from data_ingest.alpha_flow.sources import get_source as get_flow_source

        fund = FundamentalIngestService(source=get_fund_source("akshare"))
        r = fund.run(
            FundReq(kind="valuation", start=as_of, end=as_of, symbols=symbols, job_id=args.job_id)
        )
        results.append(r)
        print(f"kind={r.kind} status={r.status} fetched={r.fetched}")
        if r.status != "committed":
            failed += 1
        flow = FlowIngestService(source=get_flow_source("akshare"))
        for kind in ("dragon_tiger", "dragon_tiger_seat", "block_trade"):
            r = flow.run(
                FlowReq(kind=kind, start=as_of, end=as_of, symbols=[], job_id=args.job_id)  # type: ignore[arg-type]
            )
            results.append(r)
            print(f"kind={r.kind} status={r.status} fetched={r.fetched}")
            if r.status != "committed":
                failed += 1

    # process + DQ
    try:
        proc_results = DataProcessService().run_p0(
            ProcessRequest(
                kind="equity_1d",
                start=as_of,
                end=as_of,
                symbols=symbols,
                index_symbols=indexes,
                factor_type=args.factor_type,
                job_id=args.job_id,
            )
        )
        for pr in proc_results:
            print(f"process kind={pr.kind} status={pr.status} output={pr.output_rows}")
            if pr.status != "committed":
                failed += 1
    except Exception as exc:  # noqa: BLE001
        print(f"process failed: {exc}")
        failed += 1

    try:
        dq = DataQualityService().run_core(
            DqRequest(
                scope="CORE",
                start=as_of,
                end=as_of,
                symbols=symbols,
                index_symbols=indexes,
                factor_type=args.factor_type,
                job_id=args.job_id,
            )
        )
        print(f"dq status={dq.status} error_fails={dq.error_fails}")
        if dq.status != "passed":
            failed += 1
    except Exception as exc:  # noqa: BLE001
        print(f"dq failed: {exc}")
        failed += 1

    print(f"summary daily as_of={as_of} failed_steps={failed}/{len(results)+2}")
    return 0 if failed == 0 else 2


def cmd_alpha_news_monitor(args: argparse.Namespace) -> int:
    from data_ingest.alpha_news_monitor.models import FetchRequest
    from data_ingest.alpha_news_monitor.service import NewsIngestService
    from data_ingest.alpha_news_monitor.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.end or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")
    source = get_source(args.source)
    service = NewsIngestService(
        source=source,
        fallback_mock_on_error=not args.no_fallback,
    )
    request = FetchRequest(
        kind=args.kind,
        start=args.start,
        end=args.end,
        symbols=symbols,
        job_id=args.job_id,
        media_filters=[m.strip() for m in (getattr(args, "media", None) or []) if m.strip()],
        forum_top_n=int(getattr(args, "forum_top_n", None) or 200),
    )
    try:
        result = service.run(request)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    print(
        f"status={result.status} batch_id={result.batch_id} "
        f"fetched={result.fetched} inserted={result.inserted} "
        f"updated={result.updated} watermark={result.watermark}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_alpha_relation(args: argparse.Namespace) -> int:
    from data_ingest.alpha_relation.models import FetchRequest
    from data_ingest.alpha_relation.service import RelationIngestService
    from data_ingest.alpha_relation.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.end or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")

    board_names = [b.strip() for b in (getattr(args, "board_name", None) or []) if b.strip()]
    service = RelationIngestService(source=get_source(args.source))
    try:
        result = service.run(
            FetchRequest(
                kind=args.kind,
                start=args.start,
                end=args.end,
                symbols=symbols,
                holder_type=getattr(args, "holder_type", None) or "社保",
                board_type=getattr(args, "board_type", None) or "CONCEPT",
                board_names=board_names,
                max_pair_stocks=int(getattr(args, "max_pair_stocks", None) or 12),
                job_id=args.job_id,
            )
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_alpha_contract(args: argparse.Namespace) -> int:
    from data_ingest.alpha_contract.models import FetchRequest
    from data_ingest.alpha_contract.service import ContractIngestService
    from data_ingest.alpha_contract.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.end or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")

    if not (args.start and args.end):
        print("status=invalid message=需要 --start 与 --end")
        return 2

    service = ContractIngestService(source=get_source(args.source))
    try:
        result = service.run(
            FetchRequest(
                kind=args.kind,
                start=args.start,
                end=args.end,
                symbols=symbols,
                job_id=args.job_id,
            )
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_alpha_flow(args: argparse.Namespace) -> int:
    from data_ingest.alpha_flow.models import FetchRequest
    from data_ingest.alpha_flow.service import FlowIngestService
    from data_ingest.alpha_flow.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args, should_chunk

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.start,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")

    source = get_source(args.source)
    service = FlowIngestService(source=source)
    base = FetchRequest(
        kind=args.kind or "northbound",
        start=args.start,
        end=args.end,
        symbols=symbols,
        job_id=args.job_id,
    )
    chunking = should_chunk(
        symbols,
        chunked=getattr(args, "chunked", False),
        universe=getattr(args, "universe", None),
        chunk_size=getattr(args, "chunk_size", 15),
    )
    try:
        if args.p1:
            if not (args.start and args.end):
                print("status=invalid message=--p1 需要 --start 与 --end")
                return 2
            if not symbols:
                print("status=invalid message=--p1 需要 --symbol 或 --universe")
                return 2
            results = (
                service.run_p1_chunked(base, chunk_size=args.chunk_size)
                if chunking
                else service.run_p1(base)
            )
            committed = sum(1 for r in results if r.status == "committed")
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
            ok = committed > 0 if chunking else all(
                r.status == "committed" for r in results
            )
            print(f"summary committed_batches={committed}/{len(results)}")
            return 0 if ok else 2

        if not args.kind:
            print("status=invalid message=请指定 --kind 或使用 --p1")
            return 2
        if args.kind == "stock_flow" and chunking:
            if not symbols:
                print("status=invalid message=stock_flow 需要 --symbol 或 --universe")
                return 2
            results = service.run_stock_flow_chunked(
                base, chunk_size=args.chunk_size
            )
            committed = sum(1 for r in results if r.status == "committed")
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
            print(f"summary committed_batches={committed}/{len(results)}")
            return 0 if committed > 0 else 2
        result = service.run(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def cmd_alpha_fundamental(args: argparse.Namespace) -> int:
    from data_ingest.alpha_fundamental.models import FetchRequest
    from data_ingest.alpha_fundamental.service import FundamentalIngestService
    from data_ingest.alpha_fundamental.sources import get_source
    from shared.ingest_batching import resolve_symbols_from_args, should_chunk
    from shared.universe_resolve import symbols_missing_fund_statement

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    statement_types = [s.strip() for s in (args.statement_type or []) if s.strip()]
    try:
        sid, symbols = resolve_symbols_from_args(
            universe=getattr(args, "universe", None),
            symbols=symbols,
            as_of=getattr(args, "universe_as_of", None) or args.start or args.end,
            as_of_end=args.end,
        )
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2
    if getattr(args, "universe", None):
        print(f"universe={args.universe} snapshot_id={sid} members={len(symbols)}")

    if getattr(args, "skip_existing", False) and symbols:
        before = len(symbols)
        symbols = symbols_missing_fund_statement(symbols, min_rows=1)
        print(f"skip_existing: keep {len(symbols)}/{before} missing fund_statement")

    source = get_source(args.source)
    service = FundamentalIngestService(source=source)
    base = FetchRequest(
        kind=args.kind or "statement",
        start=args.start,
        end=args.end,
        symbols=symbols,
        statement_types=statement_types,
        job_id=args.job_id,
    )
    chunking = should_chunk(
        symbols,
        chunked=getattr(args, "chunked", False),
        universe=getattr(args, "universe", None),
        chunk_size=getattr(args, "chunk_size", 15),
    )
    try:
        if args.p1:
            if not symbols:
                if getattr(args, "skip_existing", False):
                    print("skip_existing: 无需补数，退出")
                    return 0
                print("status=invalid message=--p1 需要 --symbol 或 --universe")
                return 2
            results = (
                service.run_p1_chunked(base, chunk_size=args.chunk_size)
                if chunking
                else service.run_p1(base)
            )
            committed = sum(1 for r in results if r.status == "committed")
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
            ok = committed > 0 if chunking else all(
                r.status == "committed" for r in results
            )
            print(f"summary committed_batches={committed}/{len(results)}")
            return 0 if ok else 2

        if not args.kind:
            print("status=invalid message=请指定 --kind 或使用 --p1")
            return 2
        if args.kind in {"statement", "indicator", "valuation", "holder"}:
            if not symbols:
                if getattr(args, "skip_existing", False):
                    print("skip_existing: 无需补数，退出")
                    return 0
                print("status=invalid message=该 kind 需要 --symbol 或 --universe")
                return 2
            if chunking:
                results = service.run_symbol_kind_chunked(
                    base, chunk_size=args.chunk_size
                )
                committed = sum(1 for r in results if r.status == "committed")
                for r in results:
                    print(
                        f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                        f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                    )
                    if r.message:
                        print(f"message={r.message}")
                print(f"summary committed_batches={committed}/{len(results)}")
                return 0 if committed > 0 else 2
        result = service.run(base)
    except ValueError as exc:
        print(f"status=invalid message={exc}")
        return 2

    print(
        f"status={result.status} batch_id={result.batch_id} kind={result.kind} "
        f"fetched={result.fetched} inserted={result.inserted} updated={result.updated}"
    )
    if result.message:
        print(f"message={result.message}")
    return 0 if result.status == "committed" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A股量化 backend 入口")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mig = sub.add_parser("migrate", help="按序应用 database/migrations/*.sql")
    p_mig.set_defaults(func=cmd_migrate)

    p_ann = sub.add_parser("alpha_announcement", help="运行公告获取模块")
    p_ann.add_argument(
        "--kind",
        required=True,
        choices=[
            "ann_incremental",
            "ann_watchlist",
            "ann_backfill",
            "ann_by_category",
        ],
    )
    p_ann.add_argument(
        "--source",
        default="eastmoney",
        choices=["eastmoney", "akshare", "cninfo", "mock"],
    )
    p_ann.add_argument("--symbol", action="append", default=[])
    p_ann.add_argument(
        "--category",
        action="append",
        default=[],
        help=(
            "ann_by_category 规范化类别，可重复。"
            "中标相关: win_bid；重大合同(含中标): major_contract；"
            "另有 share_decrease/investigation/buyback 等"
        ),
    )
    p_ann.add_argument("--start", help="开始日期 YYYY-MM-DD")
    p_ann.add_argument("--end", help="结束日期 YYYY-MM-DD")
    p_ann.add_argument("--page-size", type=int, default=30)
    p_ann.add_argument("--max-pages", type=int, default=3)
    p_ann.add_argument("--job-id", default=None)
    p_ann.add_argument("--no-fallback", action="store_true")
    p_ann.set_defaults(func=cmd_alpha_announcement)

    p_ref = sub.add_parser("core_ref", help="运行 CORE 参考数据获取模块")
    p_ref.add_argument(
        "--kind",
        choices=[
            "calendar",
            "listing",
            "industry",
            "share_capital",
            "index_member",
            "special_treat",
            "restricted_release",
        ],
    )
    p_ref.add_argument(
        "--p0",
        action="store_true",
        help="按序跑齐 P0：calendar→listing→industry→share_capital",
    )
    p_ref.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_ref.add_argument("--start", help="YYYY-MM-DD（calendar/--p0 必填）")
    p_ref.add_argument("--end", help="YYYY-MM-DD（calendar/--p0 必填）")
    p_ref.add_argument("--exchange", default="SSE")
    p_ref.add_argument("--industry-standard", default="SW2021")
    p_ref.add_argument("--index", action="append", default=[], help="指数代码，可重复")
    p_ref.add_argument("--symbol", action="append", default=[], help="可选：解禁过滤标的")
    p_ref.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="restricted_release：按 Universe 过滤",
    )
    p_ref.add_argument("--universe-as-of", help="Universe 点时日")
    p_ref.add_argument(
        "--share-sh-limit",
        type=int,
        default=80,
        help="沪市股本逐票拉取上限；0=全量（较慢）",
    )
    p_ref.add_argument("--job-id", default=None)
    p_ref.set_defaults(func=cmd_core_ref)

    p_mkt = sub.add_parser("core_market", help="运行 CORE 行情获取模块")
    p_mkt.add_argument(
        "--kind",
        choices=[
            "equity_1d",
            "adj_factor",
            "suspend",
            "limit",
            "index_1d",
            "corp_action",
            "market_rank",
            "abnormal_move",
            "board_1d",
        ],
    )
    p_mkt.add_argument(
        "--p0",
        action="store_true",
        help="按序跑齐 P0：equity_1d→adj_factor→suspend→limit→index_1d",
    )
    p_mkt.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_mkt.add_argument("--start", help="YYYY-MM-DD")
    p_mkt.add_argument("--end", help="YYYY-MM-DD")
    p_mkt.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_mkt.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="从已提交 Universe 快照取标的（经库交接，不新建模块）",
    )
    p_mkt.add_argument(
        "--universe-as-of",
        help="Universe 点时日，默认用 --start",
    )
    p_mkt.add_argument(
        "--chunked",
        action="store_true",
        help="equity/adj 分块提交；--universe 或标的>30 时自动开启",
    )
    p_mkt.add_argument("--chunk-size", type=int, default=15)
    p_mkt.add_argument(
        "--chunk-months",
        type=int,
        default=0,
        help="suspend/limit/market_rank/abnormal_move/board_1d：按 N 个月分块；0=不分块",
    )
    p_mkt.add_argument(
        "--skip-existing",
        action="store_true",
        help="跳过已有数据：P0/equity 看 raw_equity_bar_1d；按日 kind 跳过已覆盖月份",
    )
    p_mkt.add_argument(
        "--min-bars",
        type=int,
        default=1,
        help="配合 --skip-existing：区间内行数 < min-bars 才补拉（长窗回填可设 500+）",
    )
    p_mkt.add_argument(
        "--index",
        action="append",
        default=[],
        help="指数代码，可重复（默认 000300）",
    )
    p_mkt.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="market_rank：各榜保留前 N（默认 100）",
    )
    p_mkt.add_argument(
        "--rank-type",
        action="append",
        default=[],
        choices=[
            "PCT_CHG_UP",
            "PCT_CHG_DOWN",
            "VOLUME",
            "AMOUNT",
            "TURNOVER",
            "HOT",
        ],
        help="market_rank：榜单类型，可重复；默认全部",
    )
    p_mkt.add_argument(
        "--prefer-spot",
        action="store_true",
        help="market_rank：--end/当日优先用 stock_zh_a_spot_em 全市场截面",
    )
    p_mkt.add_argument(
        "--change-type",
        action="append",
        default=[],
        help="abnormal_move：异动类型（如 火箭发射/大笔买入），可重复；默认全部",
    )
    p_mkt.add_argument(
        "--board-type",
        action="append",
        default=[],
        choices=["INDUSTRY", "CONCEPT"],
        help="board_1d：板块类型，可重复；默认 INDUSTRY",
    )
    p_mkt.add_argument(
        "--board-name",
        action="append",
        default=[],
        help="board_1d：板块名称过滤，可重复；默认全行业/全概念",
    )
    p_mkt.add_argument("--job-id", default=None)
    p_mkt.set_defaults(func=cmd_core_market)

    p_fund = sub.add_parser("alpha_fundamental", help="运行 ALPHA 基本面获取模块")
    p_fund.add_argument(
        "--kind",
        choices=["statement", "indicator", "consensus", "valuation", "holder"],
    )
    p_fund.add_argument(
        "--p1",
        action="store_true",
        help="按序跑齐 P1：statement→indicator",
    )
    p_fund.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_fund.add_argument("--start", help="按公告日/报告期过滤 YYYY-MM-DD")
    p_fund.add_argument("--end", help="按公告日/报告期过滤 YYYY-MM-DD")
    p_fund.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_fund.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="从 Universe 快照取标的；可与 --symbol 求交",
    )
    p_fund.add_argument(
        "--universe-as-of",
        help="Universe 点时日，默认 --start 或 --end",
    )
    p_fund.add_argument(
        "--chunked",
        action="store_true",
        help="statement/indicator 分块提交；--universe 或标的>30 时自动开启",
    )
    p_fund.add_argument("--chunk-size", type=int, default=15)
    p_fund.add_argument(
        "--skip-existing",
        action="store_true",
        help="跳过已有 raw_fund_statement 的标的",
    )
    p_fund.add_argument(
        "--statement-type",
        action="append",
        default=[],
        choices=["INCOME", "BALANCE", "CASHFLOW"],
        help="报表类型，可重复；默认三类全拉",
    )
    p_fund.add_argument("--job-id", default=None)
    p_fund.set_defaults(func=cmd_alpha_fundamental)

    p_flow = sub.add_parser("alpha_flow", help="运行 ALPHA 资金流获取模块")
    p_flow.add_argument(
        "--kind",
        choices=[
            "northbound",
            "stock_flow",
            "margin",
            "dragon_tiger",
            "dragon_tiger_seat",
            "block_trade",
        ],
    )
    p_flow.add_argument(
        "--p1",
        action="store_true",
        help="按序跑齐 P1：northbound→stock_flow",
    )
    p_flow.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_flow.add_argument("--start", help="YYYY-MM-DD")
    p_flow.add_argument("--end", help="YYYY-MM-DD")
    p_flow.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_flow.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="从 Universe 快照取标的（stock_flow/p1 需要）",
    )
    p_flow.add_argument(
        "--universe-as-of",
        help="Universe 点时日，默认 --start",
    )
    p_flow.add_argument(
        "--chunked",
        action="store_true",
        help="stock_flow 分块提交；--universe 或标的>30 时自动开启",
    )
    p_flow.add_argument("--chunk-size", type=int, default=15)
    p_flow.add_argument("--job-id", default=None)
    p_flow.set_defaults(func=cmd_alpha_flow)

    p_rel = sub.add_parser("alpha_relation", help="运行 ALPHA 个股关系边获取（图谱）")
    p_rel.add_argument(
        "--kind",
        required=True,
        choices=["hot_relate", "holder_team", "board_co"],
        help="hot_relate=人气相关股；holder_team=股东协同共持；board_co=同板块",
    )
    p_rel.add_argument(
        "--source", default="akshare", choices=["akshare", "eastmoney", "mock"]
    )
    p_rel.add_argument("--start", help="可选 YYYY-MM-DD")
    p_rel.add_argument("--end", help="as_of 日 YYYY-MM-DD，默认今天")
    p_rel.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_rel.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="hot_relate 必填之一；holder_team/board_co 用于过滤边两端",
    )
    p_rel.add_argument("--universe-as-of", help="Universe 点时日")
    p_rel.add_argument(
        "--holder-type",
        default="社保",
        choices=["社保", "基金", "QFII", "券商", "信托", "个人", "全部"],
        help="holder_team：股东类型（勿用全部，分页极多）",
    )
    p_rel.add_argument(
        "--board-type",
        default="CONCEPT",
        choices=["CONCEPT", "INDUSTRY"],
        help="board_co：概念或行业",
    )
    p_rel.add_argument(
        "--board-name",
        action="append",
        default=[],
        help="board_co：板块名称，可重复",
    )
    p_rel.add_argument(
        "--max-pair-stocks",
        type=int,
        default=12,
        help="holder_team：单条明细最多展开多少只股做完全图",
    )
    p_rel.add_argument("--job-id", default=None)
    p_rel.set_defaults(func=cmd_alpha_relation)

    p_contract = sub.add_parser(
        "alpha_contract", help="运行 ALPHA 重大合同/中标获取模块"
    )
    p_contract.add_argument(
        "--kind",
        required=True,
        choices=["win_bid", "major_contract"],
        help="win_bid=仅中标相关；major_contract=重大合同全量",
    )
    p_contract.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_contract.add_argument("--start", required=True, help="YYYY-MM-DD（公告日起）")
    p_contract.add_argument("--end", required=True, help="YYYY-MM-DD（公告日止）")
    p_contract.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_contract.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="按 Universe 过滤标的（可选）",
    )
    p_contract.add_argument("--universe-as-of", help="Universe 点时日")
    p_contract.add_argument("--job-id", default=None)
    p_contract.set_defaults(func=cmd_alpha_contract)

    p_news = sub.add_parser("alpha_news_monitor", help="运行 ALPHA 新闻/论坛监控模块")
    p_news.add_argument(
        "--kind",
        required=True,
        choices=[
            "news_incremental",
            "news_watchlist",
            "news_backfill",
            "news_official",
            "news_forum",
            "news_policy",
        ],
    )
    p_news.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_news.add_argument("--symbol", action="append", default=[])
    p_news.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="news_forum/watchlist/policy：从 Universe 过滤标的",
    )
    p_news.add_argument("--universe-as-of", help="Universe 点时日")
    p_news.add_argument("--start", help="YYYY-MM-DD")
    p_news.add_argument("--end", help="YYYY-MM-DD")
    p_news.add_argument(
        "--media",
        action="append",
        default=[],
        help=(
            "子源过滤。官方: cls/sina/futu/ths/cctv/cjzc/caixin；"
            "论坛默认 em_comment/xueqiu/weibo，扩展 em_detail/xueqiu_follow/"
            "xueqiu_deal/baidu_hot/baidu_vote；"
            "政策默认 cjzc/caixin/epu，扩展 cctv/econ/cls_policy"
        ),
    )
    p_news.add_argument(
        "--forum-top-n",
        type=int,
        default=200,
        help="news_forum/policy：无 --symbol 时截断条数（默认 200，开发机友好）",
    )
    p_news.add_argument("--job-id", default=None)
    p_news.add_argument("--no-fallback", action="store_true")
    p_news.set_defaults(func=cmd_alpha_news_monitor)

    p_proc = sub.add_parser("data_process", help="运行数据处理（raw → processed）")
    p_proc.add_argument(
        "--kind",
        choices=["equity_1d", "index_1d", "fundamental_pit"],
    )
    p_proc.add_argument(
        "--p0",
        action="store_true",
        help="按序跑齐 P0：equity_1d → index_1d",
    )
    p_proc.add_argument("--start", help="YYYY-MM-DD")
    p_proc.add_argument("--end", help="YYYY-MM-DD")
    p_proc.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_proc.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="从 Universe 快照取标的",
    )
    p_proc.add_argument("--universe-as-of", help="Universe 点时日，默认 --start")
    p_proc.add_argument(
        "--index",
        action="append",
        default=[],
        help="指数代码，可重复（默认 000300）",
    )
    p_proc.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_proc.add_argument("--preferred-source", default="akshare")
    p_proc.add_argument("--job-id", default=None)
    p_proc.set_defaults(func=cmd_data_process)

    p_dq = sub.add_parser("data_quality", help="运行数据质量门禁（processed → dq_gate）")
    p_dq.add_argument("--scope", default="CORE", choices=["CORE", "ALPHA"])
    p_dq.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_dq.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_dq.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_dq.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="从 Universe 快照取标的",
    )
    p_dq.add_argument("--universe-as-of", help="Universe 点时日，默认 --start")
    p_dq.add_argument("--index", action="append", default=[], help="指数代码，可重复")
    p_dq.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_dq.add_argument("--job-id", default=None)
    p_dq.set_defaults(func=cmd_data_quality)

    p_daily = sub.add_parser(
        "daily",
        help="交易日增量：equity/adj→suspend/limit/index→rank/异动→process→DQ",
    )
    p_daily.add_argument("--as-of", help="YYYY-MM-DD，默认今天")
    p_daily.add_argument(
        "--universe",
        default="TOP100",
        choices=list(UNIVERSE_CHOICES),
    )
    p_daily.add_argument("--index", action="append", default=[], help="默认 000300")
    p_daily.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_daily.add_argument(
        "--with-alpha",
        action="store_true",
        help="额外拉 valuation + 龙虎榜/席位/大宗",
    )
    p_daily.add_argument(
        "--force",
        action="store_true",
        help="非开市日也强制执行",
    )
    p_daily.add_argument("--job-id", default=None)
    p_daily.set_defaults(func=cmd_daily)

    p_sm = sub.add_parser("security_master", help="生成 Universe 日快照")
    p_sm.add_argument(
        "--universe",
        choices=list(UNIVERSE_CHOICES),
        help="单一宇宙；与 --p0 二选一",
    )
    p_sm.add_argument(
        "--p0",
        action="store_true",
        help="按序生成 TOP100 → SECTOR_LEADERS（本地只沉淀龙头，不全市场灌数）",
    )
    p_sm.add_argument("--as-of", required=True, help="YYYY-MM-DD 点时日")
    p_sm.add_argument("--industry-standard", default="SW2021")
    p_sm.add_argument("--preferred-source", default="akshare")
    p_sm.add_argument("--index-symbol", default="000300")
    p_sm.add_argument(
        "--strict-open-day",
        action="store_true",
        help="as-of 非开市日则失败（默认回退上一开市日）",
    )
    p_sm.add_argument("--job-id", default=None)
    p_sm.set_defaults(func=cmd_security_master)

    p_bt = sub.add_parser("backtest", help="运行 A 股约束回测")
    p_bt.add_argument(
        "--strategy",
        default="EW_HOLD",
        choices=["EW_HOLD", "EW_REBALANCE", "FACTOR_TOP_N"],
    )
    p_bt.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_bt.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_bt.add_argument("--symbol", action="append", default=[], help="显式标的；可与 universe 二选一")
    p_bt.add_argument(
        "--universe",
        default=None,
        choices=list(UNIVERSE_CHOICES),
        help="从 Universe 快照取标的（无 --symbol 时使用，默认不强制）",
    )
    p_bt.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_bt.add_argument("--cost-version", default="v1_ashare_default")
    p_bt.add_argument("--benchmark", default="000300")
    p_bt.add_argument("--cash", type=float, default=1_000_000.0)
    p_bt.add_argument(
        "--rebalance-days",
        type=int,
        default=0,
        help="EW_REBALANCE / FACTOR_TOP_N：每隔 N 个交易日再平衡",
    )
    p_bt.add_argument(
        "--factor",
        dest="research_factor",
        default=None,
        choices=["MOM_20", "VAL_PE_PCT", "FLOW_NET_5"],
        help="FACTOR_TOP_N：使用的 research 因子代码",
    )
    p_bt.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="FACTOR_TOP_N：每期持有因子值最高的 N 只",
    )
    p_bt.add_argument(
        "--no-dq-check",
        action="store_true",
        help="调试用：跳过 dq_gate（生产勿用）",
    )
    p_bt.add_argument("--job-id", default=None)
    p_bt.set_defaults(func=cmd_backtest)

    p_rs = sub.add_parser("research", help="研究因子计算 / IC 分层评估")
    p_rs.add_argument(
        "--factor",
        required=True,
        choices=["MOM_20", "VAL_PE_PCT", "FLOW_NET_5", "ALL"],
        help="基线因子；ALL=三个依次计算",
    )
    p_rs.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_rs.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_rs.add_argument(
        "--universe",
        default="TOP100",
        choices=list(UNIVERSE_CHOICES),
        help="Universe 快照代码",
    )
    p_rs.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_rs.add_argument(
        "--evaluate",
        action="store_true",
        help="对已落库因子做 RankIC / 5 分位分层（t→t+1）",
    )
    p_rs.add_argument(
        "--no-dq-check",
        action="store_true",
        help="调试用：跳过 dq_gate（生产勿用）",
    )
    p_rs.add_argument("--job-id", default=None)
    p_rs.set_defaults(func=cmd_research)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
