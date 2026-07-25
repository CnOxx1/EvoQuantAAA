from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StrategyCode = Literal["EW_HOLD", "EW_REBALANCE", "FACTOR_TOP_N"]


@dataclass
class CostParams:
    version: str
    commission_rate: float
    min_commission: float
    stamp_tax_rate: float
    slippage_rate: float
    lot_size: int = 100


@dataclass
class BacktestRequest:
    strategy_code: StrategyCode = "EW_HOLD"
    start: str = ""
    end: str = ""
    symbols: list[str] = field(default_factory=list)
    universe_code: str | None = "HS300"
    factor_type: str = "qfq"
    cost_version: str = "v1_ashare_default"
    benchmark_index: str = "000300"
    initial_cash: float = 1_000_000.0
    require_dq: bool = True
    rebalance_days: int = 0
    research_factor: str | None = None
    top_n: int = 20
    job_id: str | None = None


@dataclass
class BacktestResult:
    status: str
    run_id: str
    strategy_code: str
    start: str
    end: str
    final_nav: float = 0.0
    total_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    trade_count: int = 0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
