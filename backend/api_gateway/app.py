from __future__ import annotations

"""FastAPI 应用工厂。依赖：fastapi、uvicorn（见 requirements.txt）。"""

from typing import Any

from api_gateway.auth import check_bearer
from api_gateway.schemas import KillBody, PromoteBody, ReviewBody
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

    @app.get("/v1/executions")
    def list_executions(
        account_id: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(
            svc.list_executions(account_id=account_id, limit=limit)
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

    @app.get("/v1/research/runs")
    def list_research_runs(
        limit: int = Query(50, ge=1, le=200),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_research_runs(limit=limit))

    @app.get("/v1/ledger/accounts/{account_id}")
    def get_ledger(
        account_id: str,
        as_of: str | None = None,
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.get_ledger(account_id, as_of=as_of))

    @app.get("/v1/ops/alerts")
    def ops_alerts(
        limit: int = Query(20, ge=1, le=100),
        _: str = Depends(require_actor),
    ) -> dict[str, Any]:
        return _emit(svc.list_alerts(limit=limit))

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"ok": True, "docs": "/docs", "health": "/health", "api": "/v1"}

    return app
