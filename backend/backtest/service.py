from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from datetime import date, timedelta

from backtest.engine import run_ew_hold, run_ew_rebalance, run_factor_top_n
from backtest.models import BacktestRequest, BacktestResult
from backtest.repository import BacktestRepository

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class BacktestService:
    def __init__(self, *, repo: BacktestRepository | None = None) -> None:
        self.repo = repo or BacktestRepository()

    def run(self, request: BacktestRequest) -> BacktestResult:
        if not (request.start and request.end):
            raise ValueError("需要 --start 与 --end")
        start, end = request.start[:10], request.end[:10]
        run_id = f"bt_{uuid.uuid4().hex}"
        created = _utcnow()

        snapshot_id = None
        symbols = [s.strip() for s in request.symbols if s.strip()]
        if not symbols and request.universe_code:
            snapshot_id, symbols = self.repo.load_universe_symbols(
                universe_code=request.universe_code,
                as_of=start,
                as_of_end=end,
            )
            if not symbols:
                return BacktestResult(
                    status="failed",
                    run_id=run_id,
                    strategy_code=request.strategy_code,
                    start=start,
                    end=end,
                    message=(
                        f"Universe {request.universe_code} 在 {start}~{end} 无快照，"
                        f"请先: python main.py security_master --universe "
                        f"{request.universe_code} --as-of {start}"
                    ),
                )

        if request.require_dq:
            gate = self.repo.require_dq_passed(
                start=start, end=end, factor_type=request.factor_type
            )
            if not gate or gate.get("status") != "passed":
                return BacktestResult(
                    status="failed",
                    run_id=run_id,
                    strategy_code=request.strategy_code,
                    start=start,
                    end=end,
                    message="dq_gate 未 passed，禁止回测该区间（可用 --no-dq-check 仅调试）",
                )

        # 只回测有 processed 行情的子集（样本期常见）
        bars = self.repo.load_equity_bars(
            start=start,
            end=end,
            symbols=symbols,
            factor_type=request.factor_type,
        )
        available = sorted({str(b["symbol"]) for b in bars})
        if not available:
            return BacktestResult(
                status="failed",
                run_id=run_id,
                strategy_code=request.strategy_code,
                start=start,
                end=end,
                message="Universe 内无 processed_equity_bar_1d，请先扩行情并 data_process",
            )
        bars = [b for b in bars if str(b["symbol"]) in set(available)]

        cost = self.repo.load_cost(request.cost_version)
        index_bars = self.repo.load_index_bars(
            start=start, end=end, index_symbol=request.benchmark_index
        )

        self.repo.create_run(
            {
                "run_id": run_id,
                "strategy_code": request.strategy_code,
                "start_date": start,
                "end_date": end,
                "universe_code": request.universe_code,
                "universe_snapshot_id": snapshot_id,
                "factor_type": request.factor_type,
                "cost_version": request.cost_version,
                "benchmark_index": request.benchmark_index,
                "initial_cash": request.initial_cash,
                "dq_required": 1 if request.require_dq else 0,
                "job_id": request.job_id,
                "meta": {
                    "requested_symbols": symbols,
                    "available_symbols": available,
                    "research_factor": request.research_factor,
                    "top_n": request.top_n,
                    "rebalance_days": request.rebalance_days,
                },
                "created_at": created,
            }
        )

        try:
            if request.strategy_code == "EW_HOLD":
                out = run_ew_hold(
                    bars=bars,
                    index_bars=index_bars,
                    cost=cost,
                    initial_cash=request.initial_cash,
                )
            elif request.strategy_code == "EW_REBALANCE":
                rb = int(request.rebalance_days or 0)
                if rb <= 0:
                    raise ValueError("EW_REBALANCE 需要 --rebalance-days > 0")
                out = run_ew_rebalance(
                    bars=bars,
                    index_bars=index_bars,
                    cost=cost,
                    initial_cash=request.initial_cash,
                    rebalance_days=rb,
                )
            elif request.strategy_code == "FACTOR_TOP_N":
                if not request.research_factor:
                    raise ValueError("FACTOR_TOP_N 需要 --factor")
                if not request.universe_code:
                    raise ValueError("FACTOR_TOP_N 需要 --universe（与因子落库一致）")
                rb = int(request.rebalance_days or 0)
                if rb <= 0:
                    raise ValueError("FACTOR_TOP_N 需要 --rebalance-days > 0")
                top_n = int(request.top_n or 0)
                if top_n <= 0:
                    raise ValueError("FACTOR_TOP_N 需要 --top-n > 0")
                # 多取数日因子，供首个调仓日用「前一日」值
                factor_start = (
                    date.fromisoformat(start) - timedelta(days=40)
                ).isoformat()
                factor_rows = self.repo.load_research_factor_values(
                    factor_code=request.research_factor,
                    universe_code=request.universe_code,
                    start=factor_start,
                    end=end,
                    symbols=available,
                )
                if not factor_rows:
                    raise RuntimeError(
                        f"无因子 {request.research_factor}/{request.universe_code}，"
                        f"请先: python main.py research --factor "
                        f"{request.research_factor} --universe {request.universe_code} "
                        f"--start {start} --end {end}"
                    )
                out = run_factor_top_n(
                    bars=bars,
                    index_bars=index_bars,
                    cost=cost,
                    initial_cash=request.initial_cash,
                    factor_rows=factor_rows,
                    top_n=top_n,
                    rebalance_days=rb,
                )
            else:
                raise ValueError(f"不支持的策略: {request.strategy_code}")
            self.repo.write_nav(run_id, out.nav_rows)
            self.repo.write_trades(run_id, out.trades)
            meta = {
                "requested_symbols": symbols,
                "available_symbols": available,
                "symbols_used": out.symbols_used,
                "coverage": f"{len(out.symbols_used)}/{len(symbols)}",
                "research_factor": request.research_factor,
                "top_n": request.top_n,
                "rebalance_days": request.rebalance_days,
            }
            self.repo.finish_run(
                run_id=run_id,
                status="committed",
                stats={
                    "final_nav": out.final_nav,
                    "total_return": out.total_return,
                    "benchmark_return": out.benchmark_return,
                    "max_drawdown": out.max_drawdown,
                    "trade_count": len(out.trades),
                    "meta": meta,
                },
                finished_at=_utcnow(),
            )
            logger.info(
                "backtest committed run=%s ret=%.4f bench=%.4f trades=%s",
                run_id,
                out.total_return,
                out.benchmark_return,
                len(out.trades),
            )
            return BacktestResult(
                status="committed",
                run_id=run_id,
                strategy_code=request.strategy_code,
                start=start,
                end=end,
                final_nav=out.final_nav,
                total_return=out.total_return,
                benchmark_return=out.benchmark_return,
                max_drawdown=out.max_drawdown,
                trade_count=len(out.trades),
                meta=meta,
                message=f"coverage={meta['coverage']}",
            )
        except Exception as exc:
            logger.exception("backtest failed")
            self.repo.finish_run(
                run_id=run_id,
                status="failed",
                stats={"error_message": str(exc)},
                finished_at=_utcnow(),
            )
            return BacktestResult(
                status="failed",
                run_id=run_id,
                strategy_code=request.strategy_code,
                start=start,
                end=end,
                message=str(exc),
            )
