from __future__ import annotations

"""FastAPI 应用工厂。依赖：fastapi、uvicorn（见 requirements.txt）。"""

from typing import Any

from api_gateway.auth import check_bearer
from api_gateway.schemas import (
    BacktestRunBody,
    ExecutionRunBody,
    FactorDefBody,
    FactorDefPatchBody,
    KillBody,
    LedgerPostBody,
    PortfolioBuildBody,
    PromoteBody,
    RegisterBody,
    ResearchRunBody,
    ResumePendingBody,
    ReviewBody,
    ScheduleOnceBody,
    SignalRunBody,
)
from api_gateway.service import GatewayService


def create_app() -> Any:
    try:
        from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "需要安装 fastapi/uvicorn：pip install fastapi uvicorn"
        ) from exc

    app = FastAPI(
        title="EvoQuantAAA API Gateway",
        version="0.1.0",
        description="查询 / Kill Switch / 策略晋升 / 风控审核入口",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8081",
            "http://localhost:8081",
            "null",  # file:// 打开 console
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    svc = GatewayService()

    def require_actor(
        authorization: str | None = Header(default=None),
    ) -> str:
        allowed, info = check_bearer(authorization)
        if not allowed:
            raise HTTPException(status_code=401, detail=info or "unauthorized")
        return info or "anonymous"

    def _emit(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("ok"):
            return body
        err = body.get("error") or {}
        status = int(err.get("status") or 400)
        raise HTTPException(status_code=status, detail=body)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "api_gateway"}

    @app.get("/v1/strategies")
    def list_strategies(
        status: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_strategies(status=status, limit=limit))

    @app.get("/v1/strategies/{strategy_version}")
    def get_strategy(
        strategy_version: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_strategy(strategy_version))

    @app.post("/v1/strategies")
    def register_strategy(
        payload: RegisterBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.register_strategy(
                strategy_code=payload.strategy_code,
                strategy_kind=payload.strategy_kind,
                factor_code=payload.factor_code,
                top_n=payload.top_n,
                rebalance_days=payload.rebalance_days,
                universe_code=payload.universe_code,
                factor_type=payload.factor_type,
                research_run_id=payload.research_run_id,
                backtest_run_id=payload.backtest_run_id,
                note=payload.note,
                actor=actor,
            )
        )

    @app.post("/v1/strategies/{strategy_version}/promote")
    def promote_strategy(
        strategy_version: str,
        payload: PromoteBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.promote_strategy(
                strategy_version=strategy_version,
                to_status=payload.to,
                backtest_run=payload.backtest_run,
                reason=payload.reason,
                actor=actor,
                skip_gates=payload.skip_gates,
                gate_version=payload.gate_version,
            )
        )

    @app.get("/v1/signal/batches")
    def signal_batches(
        strategy_version: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_signal_batches(
                strategy_version=strategy_version, limit=limit
            )
        )

    @app.post("/v1/signal/run")
    def signal_run(
        payload: SignalRunBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.run_signal(
                as_of=payload.as_of,
                strategy_version=payload.strategy_version,
                paper=payload.paper,
                live=payload.live,
                require_dq=payload.require_dq,
                actor=actor,
            )
        )

    @app.get("/v1/portfolios")
    def list_portfolios(
        status: str | None = None,
        as_of: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_portfolios(status=status, as_of=as_of, limit=limit)
        )

    @app.post("/v1/portfolios/build")
    def portfolios_build(
        payload: PortfolioBuildBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.build_portfolio(
                as_of=payload.as_of,
                strategy_version=payload.strategy_version,
                account_id=payload.account_id,
                paper=payload.paper,
                live=payload.live,
                nav=payload.nav,
                use_ledger_nav=payload.use_ledger_nav,
                force=payload.force,
                signal_batch_id=payload.signal_batch_id,
                actor=actor,
            )
        )

    @app.get("/v1/portfolios/{portfolio_id}")
    def get_portfolio(
        portfolio_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_portfolio(portfolio_id))

    @app.get("/v1/risk/kill")
    def risk_kill_status(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.risk_status())

    @app.post("/v1/risk/kill")
    def risk_kill_set(
        payload: KillBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.set_kill(
                scope=payload.scope,
                is_on=payload.is_on,
                reason=payload.reason,
                actor=actor,
            )
        )

    @app.post("/v1/risk/review")
    def risk_review(
        payload: ReviewBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.risk_review(
                portfolio_id=payload.portfolio_id,
                drafts=payload.drafts,
                as_of=payload.as_of,
                actor=actor,
                force=payload.force,
            )
        )

    @app.get("/v1/risk/decisions")
    def risk_decisions(
        portfolio_id: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_decisions(portfolio_id=portfolio_id, limit=limit)
        )

    @app.get("/v1/risk/decisions/{decision_id}")
    def risk_decision_detail(
        decision_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_decision(decision_id))

    @app.get("/v1/executions")
    def list_executions(
        account_id: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_executions(account_id=account_id, limit=limit)
        )

    @app.post("/v1/executions/run")
    def executions_run(
        payload: ExecutionRunBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.run_execution(
                portfolio_id=payload.portfolio_id,
                approved=payload.approved,
                as_of=payload.as_of,
                account_id=payload.account_id,
                adapter=payload.adapter,
                force=payload.force,
                actor=actor,
            )
        )

    @app.get("/v1/executions/{execution_id}")
    def get_execution(
        execution_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_execution(execution_id))

    @app.get("/v1/execution/pending")
    def list_pending(
        account_id: str | None = None,
        status: str | None = "open",
        limit: int = Query(100, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_pending(
                account_id=account_id, status=status, limit=limit
            )
        )

    @app.post("/v1/execution/pending/resume")
    def pending_resume(
        payload: ResumePendingBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.resume_pending(
                as_of=payload.as_of,
                account_id=payload.account_id,
                adapter=payload.adapter,
                strategy_version=payload.strategy_version,
                actor=actor,
            )
        )

    @app.get("/v1/research/runs")
    def list_research_runs(
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_research_runs(limit=limit))

    @app.get("/v1/research/runs/{run_id}")
    def research_run_detail(
        run_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_research_run(run_id))

    @app.get("/v1/backtest/runs")
    def list_backtests(
        status: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_backtest_runs(status=status, limit=limit))

    @app.post("/v1/backtest/runs")
    def run_backtest(
        payload: BacktestRunBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.run_backtest(
                strategy=payload.strategy,
                start=payload.start,
                end=payload.end,
                universe=payload.universe,
                factor_type=payload.factor_type,
                factor=payload.factor,
                top_n=payload.top_n,
                rebalance_days=payload.rebalance_days,
                benchmark=payload.benchmark,
                cash=payload.cash,
                require_dq=payload.require_dq,
                cost_version=payload.cost_version,
                actor=actor,
            )
        )

    @app.get("/v1/backtest/runs/{run_id}")
    def backtest_detail(
        run_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_backtest_run(run_id))

    @app.get("/v1/market/search")
    def market_search(
        q: str = Query(..., min_length=1, max_length=64),
        as_of: str | None = None,
        limit: int = Query(20, ge=1, le=50),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.search_securities(q=q, as_of=as_of, limit=limit))

    @app.get("/v1/market/boards")
    def market_boards(
        trade_date: str | None = None,
        board_type: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_boards(
                trade_date=trade_date, board_type=board_type, limit=limit
            )
        )

    @app.get("/v1/market/boards/history")
    def market_board_history(
        board_name: str = Query(..., min_length=1),
        board_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = Query(120, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_board_history(
                board_name=board_name,
                board_type=board_type,
                start=start,
                end=end,
                limit=limit,
            )
        )

    @app.get("/v1/market/boards/members")
    def market_board_members(
        industry_name: str | None = None,
        industry_code: str | None = None,
        as_of: str | None = None,
        limit: int = Query(200, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_board_members(
                industry_name=industry_name,
                industry_code=industry_code,
                as_of=as_of,
                limit=limit,
            )
        )

    @app.get("/v1/market/events")
    def market_events(
        start: str | None = None,
        end: str | None = None,
        symbol: str | None = None,
        limit: int = Query(100, ge=1, le=300),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_market_events(
                start=start, end=end, symbol=symbol, limit=limit
            )
        )

    @app.get("/v1/market/calendar")
    def market_calendar(
        start: str | None = None,
        end: str | None = None,
        limit: int = Query(100, ge=1, le=300),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_econ_calendar(start=start, end=end, limit=limit)
        )

    @app.get("/v1/market/f10/{symbol}")
    def market_f10(
        symbol: str,
        as_of: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.get_f10(symbol, as_of=as_of))

    @app.get("/v1/data/dq/runs")
    def dq_runs(
        scope: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_dq_runs(scope=scope, limit=limit))

    @app.get("/v1/data/dq/runs/{dq_run_id}")
    def dq_run_detail(
        dq_run_id: str, _: str = Depends(require_actor)
    ) -> dict[str, Any]:
        return _emit(svc.get_dq_run(dq_run_id))

    @app.get("/v1/data/dq/gates")
    def dq_gates(
        scope: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_dq_gates(scope=scope, limit=limit))

    @app.get("/v1/data/coverage")
    def data_coverage(
        start: str = Query(..., min_length=8, max_length=10),
        end: str = Query(..., min_length=8, max_length=10),
        symbols: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.data_coverage(start=start, end=end, symbols=symbols))

    @app.get("/v1/market/ranks/meta")
    def market_ranks_meta(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.market_rank_meta())

    @app.get("/v1/market/ranks")
    def market_ranks(
        trade_date: str | None = None,
        rank_type: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_market_ranks(
                trade_date=trade_date, rank_type=rank_type, limit=limit
            )
        )

    @app.get("/v1/market/abnormal")
    def market_abnormal(
        trade_date: str | None = None,
        change_type: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_abnormal_moves(
                trade_date=trade_date, change_type=change_type, limit=limit
            )
        )

    @app.get("/v1/market/news")
    def market_news(
        channel: str | None = None,
        symbol: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_news(channel=channel, symbol=symbol, limit=limit)
        )

    @app.get("/v1/market/dragon-tiger")
    def market_dragon_tiger(
        trade_date: str | None = None,
        limit: int = Query(100, ge=1, le=300),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_dragon_tiger(trade_date=trade_date, limit=limit)
        )

    @app.get("/v1/market/bars")
    def market_bars(
        symbol: str = Query(..., min_length=1, max_length=16),
        start: str | None = None,
        end: str | None = None,
        factor_type: str = Query("qfq"),
        freq: str = Query("1d", description="1d | 15m | 60m"),
        limit: int = Query(120, ge=1, le=2000),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        """K 线：日线 processed_equity_bar_1d；分钟线 processed_equity_bar_min。"""
        return _emit(
            svc.list_equity_bars(
                symbol=symbol,
                start=start,
                end=end,
                factor_type=factor_type,
                freq=freq,
                limit=limit,
            )
        )

    @app.get("/v1/market/indicators/meta")
    def market_indicators_meta(
        symbol: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.tech_indicator_meta(symbol=symbol))

    @app.get("/v1/market/indicators")
    def market_indicators(
        symbol: str = Query(..., min_length=1, max_length=16),
        codes: str | None = Query(
            None, description="逗号分隔，默认 core：MA/MACD/RSI/BOLL"
        ),
        start: str | None = None,
        end: str | None = None,
        factor_type: str = Query("qfq"),
        limit: int = Query(180, ge=1, le=800),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        """日线技术指标（processed_tech_indicator_1d）。"""
        return _emit(
            svc.list_tech_indicators(
                symbol=symbol,
                codes=codes,
                start=start,
                end=end,
                factor_type=factor_type,
                limit=limit,
            )
        )

    @app.get("/v1/ledger/accounts/{account_id}")
    def get_ledger(
        account_id: str,
        as_of: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.get_ledger(account_id, as_of=as_of))

    @app.post("/v1/ledger/post")
    def ledger_post(
        payload: LedgerPostBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.post_ledger(
                execution_id=payload.execution_id,
                account_id=payload.account_id,
                force=payload.force,
                actor=actor,
            )
        )

    @app.get("/v1/ops/alerts")
    def ops_alerts(
        limit: int = Query(20, ge=1, le=100),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_alerts(limit=limit))

    @app.get("/v1/ops/pipeline")
    def ops_pipeline(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.ops_pipeline())

    @app.get("/v1/modules")
    def modules(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_modules())

    @app.get("/v1/signal/batches/{signal_batch_id}")
    def signal_batch_detail(
        signal_batch_id: str,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.get_signal_batch(signal_batch_id))

    @app.get("/v1/universe/snapshots")
    def universe_snapshots(
        universe_code: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_universe_snapshots(universe_code=universe_code, limit=limit)
        )

    @app.get("/v1/universe/snapshots/{universe_snapshot_id}")
    def universe_snapshot_detail(
        universe_snapshot_id: str,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.get_universe_snapshot(universe_snapshot_id))

    @app.get("/v1/data/ingest/batches")
    def ingest_batches(
        lane: str | None = None,
        module: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_ingest_batches(lane=lane, module=module, limit=limit)
        )

    @app.get("/v1/execution/adapters")
    def execution_adapters(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_execution_adapters())

    @app.get("/v1/research/freezes")
    def research_freezes(
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_evidence_freezes(limit=limit))

    @app.get("/v1/data/process/batches")
    def process_batches(
        kind: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_process_batches(kind=kind, limit=limit))

    @app.get("/v1/ref/cost-params")
    def cost_params(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_cost_params())

    @app.get("/v1/ref/risk-limits")
    def risk_limits(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_risk_limits())

    @app.get("/v1/ref/promotion-gates")
    def promotion_gates(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_promotion_gate_params())

    @app.get("/v1/ref/promotion-gate-results")
    def promotion_gate_results(
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_promotion_gate_results(limit=limit))

    @app.get("/v1/ledger/capital-alloc")
    def capital_alloc(
        account_id: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_capital_alloc(account_id=account_id))

    @app.get("/v1/research/factors")
    def research_factors(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_factor_catalog())

    @app.get("/v1/research/factor-defs")
    def research_factor_defs(
        status: str | None = Query("ACTIVE"),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_factor_defs(status=status))

    @app.post("/v1/research/factor-defs")
    def research_factor_defs_create(
        payload: FactorDefBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.register_factor_def(
                factor_code=payload.factor_code,
                template=payload.template,
                params=payload.params or {},
                display_name=payload.display_name,
                description=payload.description,
                status=payload.status,
                actor=actor,
            )
        )

    @app.patch("/v1/research/factor-defs/{factor_code}")
    def research_factor_defs_patch(
        factor_code: str,
        payload: FactorDefPatchBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.update_factor_def(
                factor_code,
                display_name=payload.display_name,
                params=payload.params,
                description=payload.description,
                status=payload.status,
                actor=actor,
            )
        )

    @app.post("/v1/research/runs")
    def research_runs_create(
        payload: ResearchRunBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.run_research_factor(
                factor_code=payload.factor_code,
                start=payload.start,
                end=payload.end,
                universe_code=payload.universe_code,
                factor_type=payload.factor_type,
                require_dq=payload.require_dq,
                actor=actor,
            )
        )

    @app.get("/v1/research/factors/{factor_code}/values")
    def research_factor_values(
        factor_code: str,
        universe_code: str | None = None,
        as_of: str | None = None,
        limit: int = Query(200, ge=1, le=500),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_factor_values(
                factor_code=factor_code,
                universe_code=universe_code,
                as_of=as_of,
                limit=limit,
            )
        )

    @app.get("/v1/ops/audit")
    def ops_audit(
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_audit_logs(limit=limit))

    @app.get("/v1/ops/activity")
    def ops_activity(
        limit: int = Query(40, ge=1, le=100),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_ops_activity(limit=limit))

    @app.post("/v1/ops/schedule/once")
    def ops_schedule_once(
        payload: ScheduleOnceBody = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.run_schedule_once(
                as_of=payload.as_of,
                universe=payload.universe,
                factor_type=payload.factor_type,
                force=payload.force,
                actor=actor,
            )
        )

    @app.get("/v1/ledger/accounts")
    def ledger_accounts(_: str = Depends(require_actor)) -> dict[str, Any]:
        return _emit(svc.list_ledger_accounts())

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"ok": True, "docs": "/docs", "health": "/health", "api": "/v1"}

    return app
