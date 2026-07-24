from __future__ import annotations

"""
后端入口。

示例：
  cd backend
  python main.py migrate
  python main.py core_ref --kind calendar --start 2026-07-01 --end 2026-07-31
  python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
  python main.py core_market --p0 --start 2026-07-21 --end 2026-07-23 --symbol 600000 --symbol 000001
  python main.py alpha_fundamental --p1 --symbol 600000 --statement-type INCOME
  python main.py alpha_flow --p1 --start 2024-08-01 --end 2024-08-16 --symbol 600000
  python main.py alpha_news_monitor --kind news_incremental
  python main.py alpha_announcement --kind ann_incremental --source eastmoney
  python main.py data_process --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
  python main.py data_quality --scope CORE --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
  python main.py security_master --p0 --as-of 2026-07-23
  python main.py backtest --strategy EW_HOLD --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
"""

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    if args.scope != "CORE":
        print("status=invalid message=当前仅支持 --scope CORE")
        return 2
    try:
        result = DataQualityService().run_core(
            DqRequest(
                scope="CORE",
                start=args.start,
                end=args.end,
                symbols=symbols,
                index_symbols=indexes,
                factor_type=args.factor_type,
                job_id=args.job_id,
            )
        )
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

    indexes = [s.strip() for s in (args.index or []) if s.strip()]
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
    from shared.universe_resolve import (
        resolve_universe_symbols,
        symbols_missing_equity_bars,
    )

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    indexes = [s.strip() for s in (args.index or []) if s.strip()]
    if args.universe:
        if not args.start:
            print("status=invalid message=--universe 需要 --start（点时）")
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

    if args.skip_existing and args.start and args.end and symbols:
        before = len(symbols)
        symbols = symbols_missing_equity_bars(
            symbols, start=args.start, end=args.end, min_rows=1
        )
        print(f"skip_existing: keep {len(symbols)}/{before} missing equity bars")

    source = get_source(args.source)
    service = CoreMarketIngestService(source=source)
    base = FetchRequest(
        kind=args.kind or "equity_1d",
        start=args.start,
        end=args.end,
        symbols=symbols,
        index_symbols=indexes,
        job_id=args.job_id,
    )
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
                for kind in ("suspend", "limit", "index_1d"):
                    req = FetchRequest(
                        kind=kind,  # type: ignore[arg-type]
                        start=args.start,
                        end=args.end,
                        symbols=[],
                        index_symbols=indexes or ["000300"],
                        job_id=args.job_id,
                    )
                    results.append(service.run(req))
            elif args.chunked or args.universe or len(symbols) > 30:
                results = service.run_p0_chunked(base, chunk_size=args.chunk_size)
            else:
                results = service.run_p0(base)
            ok = True
            committed = 0
            for r in results:
                print(
                    f"kind={r.kind} status={r.status} batch_id={r.batch_id} "
                    f"fetched={r.fetched} inserted={r.inserted} updated={r.updated}"
                )
                if r.message:
                    print(f"message={r.message}")
                if r.status == "committed":
                    committed += 1
                elif r.kind in ("suspend", "limit", "index_1d"):
                    ok = False
            # 分块模式下允许部分 equity/adj chunk 失败
            if args.chunked or args.universe or len(base.symbols) > 30:
                ok = committed > 0
            else:
                ok = all(r.status == "committed" for r in results)
            print(f"summary committed_batches={committed}/{len(results)}")
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


def cmd_alpha_news_monitor(args: argparse.Namespace) -> int:
    from data_ingest.alpha_news_monitor.models import FetchRequest
    from data_ingest.alpha_news_monitor.service import NewsIngestService
    from data_ingest.alpha_news_monitor.sources import get_source

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
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


def cmd_alpha_flow(args: argparse.Namespace) -> int:
    from data_ingest.alpha_flow.models import FetchRequest
    from data_ingest.alpha_flow.service import FlowIngestService
    from data_ingest.alpha_flow.sources import get_source

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    source = get_source(args.source)
    service = FlowIngestService(source=source)
    base = FetchRequest(
        kind=args.kind or "northbound",
        start=args.start,
        end=args.end,
        symbols=symbols,
        job_id=args.job_id,
    )
    try:
        if args.p1:
            if not (args.start and args.end):
                print("status=invalid message=--p1 需要 --start 与 --end")
                return 2
            if not symbols:
                print("status=invalid message=--p1 需要至少一个 --symbol")
                return 2
            results = service.run_p1(base)
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
            print("status=invalid message=请指定 --kind 或使用 --p1")
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


def cmd_alpha_fundamental(args: argparse.Namespace) -> int:
    from data_ingest.alpha_fundamental.models import FetchRequest
    from data_ingest.alpha_fundamental.service import FundamentalIngestService
    from data_ingest.alpha_fundamental.sources import get_source

    symbols = [s.strip() for s in (args.symbol or []) if s.strip()]
    statement_types = [s.strip() for s in (args.statement_type or []) if s.strip()]
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
    try:
        if args.p1:
            if not symbols:
                print("status=invalid message=--p1 需要至少一个 --symbol")
                return 2
            results = service.run_p1(base)
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
            print("status=invalid message=请指定 --kind 或使用 --p1")
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
    p_ann.add_argument("--category", action="append", default=[])
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
        choices=["ALL_LISTED", "HS300", "HS300_EX_ST"],
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
        "--skip-existing",
        action="store_true",
        help="跳过区间内已有 raw_equity_bar_1d 的标的",
    )
    p_mkt.add_argument(
        "--index",
        action="append",
        default=[],
        help="指数代码，可重复（默认 000300）",
    )
    p_mkt.add_argument("--job-id", default=None)
    p_mkt.set_defaults(func=cmd_core_market)

    p_fund = sub.add_parser("alpha_fundamental", help="运行 ALPHA 基本面获取模块")
    p_fund.add_argument(
        "--kind",
        choices=["statement", "indicator", "consensus"],
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
    p_flow.add_argument("--job-id", default=None)
    p_flow.set_defaults(func=cmd_alpha_flow)

    p_news = sub.add_parser("alpha_news_monitor", help="运行 ALPHA 新闻监控模块")
    p_news.add_argument(
        "--kind",
        required=True,
        choices=["news_incremental", "news_watchlist", "news_backfill"],
    )
    p_news.add_argument(
        "--source",
        default="akshare",
        choices=["akshare", "eastmoney", "mock"],
    )
    p_news.add_argument("--symbol", action="append", default=[])
    p_news.add_argument("--start", help="YYYY-MM-DD")
    p_news.add_argument("--end", help="YYYY-MM-DD")
    p_news.add_argument("--job-id", default=None)
    p_news.add_argument("--no-fallback", action="store_true")
    p_news.set_defaults(func=cmd_alpha_news_monitor)

    p_proc = sub.add_parser("data_process", help="运行数据处理（raw → processed）")
    p_proc.add_argument("--kind", choices=["equity_1d", "index_1d"])
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
        choices=["ALL_LISTED", "HS300", "HS300_EX_ST"],
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
    p_dq.add_argument("--scope", default="CORE", choices=["CORE"])
    p_dq.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_dq.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_dq.add_argument("--symbol", action="append", default=[], help="股票代码，可重复")
    p_dq.add_argument("--index", action="append", default=[], help="指数代码，可重复")
    p_dq.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_dq.add_argument("--job-id", default=None)
    p_dq.set_defaults(func=cmd_data_quality)

    p_sm = sub.add_parser("security_master", help="生成 Universe 日快照")
    p_sm.add_argument(
        "--universe",
        choices=["ALL_LISTED", "HS300", "HS300_EX_ST"],
        help="单一宇宙；与 --p0 二选一",
    )
    p_sm.add_argument(
        "--p0",
        action="store_true",
        help="按序生成 ALL_LISTED → HS300 → HS300_EX_ST",
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
    p_bt.add_argument("--strategy", default="EW_HOLD", choices=["EW_HOLD"])
    p_bt.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_bt.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_bt.add_argument("--symbol", action="append", default=[], help="显式标的；可与 universe 二选一")
    p_bt.add_argument(
        "--universe",
        default=None,
        choices=["ALL_LISTED", "HS300", "HS300_EX_ST"],
        help="从 Universe 快照取标的（无 --symbol 时使用，默认不强制）",
    )
    p_bt.add_argument("--factor-type", default="qfq", choices=["qfq", "hfq"])
    p_bt.add_argument("--cost-version", default="v1_ashare_default")
    p_bt.add_argument("--benchmark", default="000300")
    p_bt.add_argument("--cash", type=float, default=1_000_000.0)
    p_bt.add_argument(
        "--no-dq-check",
        action="store_true",
        help="调试用：跳过 dq_gate（生产勿用）",
    )
    p_bt.add_argument("--job-id", default=None)
    p_bt.set_defaults(func=cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
