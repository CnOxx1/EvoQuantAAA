from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from portfolio_construct.models import PortfolioBuildRequest, PortfolioBuildResult
from portfolio_construct.repository import PortfolioRepository
from portfolio_construct.sizing import size_positions

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class PortfolioConstructService:
    def __init__(self, *, repo: PortfolioRepository | None = None) -> None:
        self.repo = repo or PortfolioRepository()

    def build(self, request: PortfolioBuildRequest) -> PortfolioBuildResult:
        as_of = (request.as_of or "")[:10]
        if not as_of:
            return PortfolioBuildResult(status="invalid", message="需要 --as-of")
        if request.nav <= 0 and not request.use_ledger_nav:
            return PortfolioBuildResult(status="invalid", message="nav 必须 > 0")

        portfolio_id = f"pf_{uuid.uuid4().hex}"
        created = _utcnow()

        strat = self.repo.load_strategy(request.strategy_version)
        if not strat:
            return PortfolioBuildResult(
                status="failed",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                as_of=as_of,
                message="strategy_version 不存在",
            )
        code = str(strat["strategy_code"])
        st = str(strat["status"])
        if request.require_runnable and st not in ("PAPER", "LIVE"):
            return PortfolioBuildResult(
                status="failed",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message=f"仅 PAPER/LIVE 可构建组合，当前={st}",
            )

        params: dict[str, Any] = dict(strat.get("params") or {})
        factor_type = str(params.get("factor_type") or "qfq")
        universe_code = str(params.get("universe_code") or "")

        existing = self.repo.find_active_target(
            strategy_version=request.strategy_version,
            as_of=as_of,
            account_id=request.account_id,
        )
        if existing and not request.force:
            return PortfolioBuildResult(
                status="skipped",
                portfolio_id=str(existing["portfolio_id"]),
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                row_count=int(existing.get("row_count") or 0),
                invested_value=float(existing.get("invested_value") or 0),
                cash_residual=float(existing.get("cash_residual") or 0),
                message=f"同日已有活跃组合 status={existing.get('status')}",
                meta={"idempotent": True},
            )

        nav = float(request.nav)
        if request.use_ledger_nav:
            estimated = float(
                self.repo.estimate_account_nav(
                    account_id=request.account_id,
                    as_of=as_of,
                    factor_type=factor_type,
                )
            )
            if estimated > 0:
                nav = estimated
            # 无账本时回退 --nav
        if nav <= 0:
            return PortfolioBuildResult(
                status="failed",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message="nav 无效，无法 sizing",
            )

        sig_date, sig_batch, weights = self.repo.load_latest_signal_weights(
            strategy_version=request.strategy_version,
            as_of=as_of,
            signal_batch_id=request.signal_batch_id,
        )
        if not weights or not sig_date:
            return PortfolioBuildResult(
                status="skipped",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message=f"as_of={as_of} 无可用 committed signal_prod_weight",
            )

        if request.require_signal_as_of and str(sig_date)[:10] != as_of:
            return PortfolioBuildResult(
                status="skipped",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message=(
                    f"非调仓日 hold：signal_trade_date={sig_date} != as_of={as_of}"
                ),
                meta={
                    "hold": True,
                    "signal_trade_date": sig_date,
                    "signal_batch_id": sig_batch,
                },
            )

        symbols = [str(w["symbol"]) for w in weights]
        bars = self.repo.load_bars_as_of(
            as_of=as_of, symbols=symbols, factor_type=factor_type
        )
        prices: dict[str, float] = {}
        can_buy: dict[str, int] = {}
        can_sell: dict[str, int] = {}
        for s, b in bars.items():
            px = b.get("close")
            if px is None:
                px = b.get("adj_close")
            if px is not None:
                prices[s] = float(px)
            can_buy[s] = int(b["can_buy"]) if b.get("can_buy") is not None else 0
            can_sell[s] = int(b["can_sell"]) if b.get("can_sell") is not None else 1

        try:
            lot_size = self.repo.load_lot_size(request.cost_version)
        except RuntimeError as exc:
            return PortfolioBuildResult(
                status="failed",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message=str(exc),
            )

        meta: dict[str, Any] = {
            "signal_trade_date": sig_date,
            "signal_batch_id": sig_batch,
            "factor_type": factor_type,
            "universe_code": universe_code,
            "strategy_status": st,
            "job_id": request.job_id,
            "use_ledger_nav": request.use_ledger_nav,
            "nav": nav,
            "pricing": "unadjusted_close",
            "capital_weight": request.capital_weight,
        }
        self.repo.create_target(
            {
                "portfolio_id": portfolio_id,
                "strategy_version": request.strategy_version,
                "signal_batch_id": sig_batch,
                "signal_trade_date": sig_date,
                "as_of_date": as_of,
                "account_id": request.account_id,
                "status": "running",
                "nav": nav,
                "cost_version": request.cost_version,
                "universe_code": universe_code or None,
                "row_count": 0,
                "job_id": request.job_id,
                "meta": meta,
                "created_at": created,
            }
        )

        try:
            positions, size_meta = size_positions(
                weight_rows=weights,
                prices=prices,
                can_buy=can_buy,
                can_sell=can_sell,
                nav=nav,
                lot_size=lot_size,
            )
            meta.update(size_meta)
            if not positions:
                self.repo.finish_target(
                    portfolio_id=portfolio_id,
                    status="failed",
                    row_count=0,
                    invested_value=0.0,
                    cash_residual=nav,
                    finished_at=_utcnow(),
                    error_message="sizing 后无持仓（缺价或不可买）",
                    meta=meta,
                )
                return PortfolioBuildResult(
                    status="failed",
                    portfolio_id=portfolio_id,
                    strategy_version=request.strategy_version,
                    strategy_code=code,
                    as_of=as_of,
                    message="sizing 后无持仓（缺价或不可买）",
                    meta=meta,
                )

            n = self.repo.upsert_positions(
                portfolio_id=portfolio_id,
                rows=positions,
                created_at=created,
            )
            invested = float(size_meta["invested_value"])
            cash = float(size_meta["cash_residual"])
            self.repo.finish_target(
                portfolio_id=portfolio_id,
                status="draft",
                row_count=n,
                invested_value=invested,
                cash_residual=cash,
                finished_at=_utcnow(),
                meta=meta,
            )
            logger.info(
                "portfolio draft portfolio_id=%s version=%s rows=%s invested=%.2f",
                portfolio_id,
                request.strategy_version,
                n,
                invested,
            )
            return PortfolioBuildResult(
                status="draft",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                row_count=n,
                invested_value=invested,
                cash_residual=cash,
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("portfolio build failed")
            self.repo.finish_target(
                portfolio_id=portfolio_id,
                status="failed",
                row_count=0,
                invested_value=0.0,
                cash_residual=nav,
                finished_at=_utcnow(),
                error_message=str(exc),
                meta=meta,
            )
            return PortfolioBuildResult(
                status="failed",
                portfolio_id=portfolio_id,
                strategy_version=request.strategy_version,
                strategy_code=code,
                as_of=as_of,
                message=str(exc),
            )

    def build_all_runnable(
        self,
        *,
        as_of: str,
        nav: float,
        account_id: str = "paper_default",
        cost_version: str = "v1_ashare_default",
        statuses: set[str] | None = None,
        job_id: str | None = None,
        use_ledger_nav: bool = True,
        force: bool = False,
    ) -> list[PortfolioBuildResult]:
        versions = self.repo.list_runnable_versions(statuses=statuses)
        if not versions:
            return [
                PortfolioBuildResult(
                    status="skipped", message="无 PAPER/LIVE 策略可构建组合"
                )
            ]
        svs = [str(v["strategy_version"]) for v in versions]
        weights = self.repo.load_capital_weights(
            account_id=account_id, strategy_versions=svs
        )
        # 先估账户总 NAV，再按 capital_weight 切分，避免多策略各吃满仓
        base_nav = float(nav)
        if use_ledger_nav:
            # 取首策略 params 的 factor_type 估权益（缺价回退 adj）
            sample_params = dict(versions[0].get("params") or {})
            ft = str(sample_params.get("factor_type") or "qfq")
            estimated = float(
                self.repo.estimate_account_nav(
                    account_id=account_id, as_of=as_of, factor_type=ft
                )
            )
            if estimated > 0:
                base_nav = estimated
        if base_nav <= 0:
            return [
                PortfolioBuildResult(
                    status="failed", message="账户 NAV 无效，无法按配额 sizing"
                )
            ]
        out: list[PortfolioBuildResult] = []
        for v in versions:
            sv = str(v["strategy_version"])
            cw = float(weights.get(sv) or 0.0)
            alloc_nav = base_nav * cw
            out.append(
                self.build(
                    PortfolioBuildRequest(
                        strategy_version=sv,
                        as_of=as_of,
                        nav=alloc_nav,
                        account_id=account_id,
                        cost_version=cost_version,
                        job_id=job_id,
                        use_ledger_nav=False,
                        capital_weight=cw,
                        force=force,
                        require_signal_as_of=True,
                    )
                )
            )
        return out
