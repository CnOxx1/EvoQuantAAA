from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AdapterKind = Literal["paper"]


@dataclass
class CostSnapshot:
    version: str
    commission_rate: float
    min_commission: float
    stamp_tax_rate: float
    slippage_rate: float
    lot_size: int = 100
    impact_model: str = "flat"
    impact_coef: float = 0.0
    adv_lookback_days: int = 20

    @property
    def needs_adv(self) -> bool:
        return (self.impact_model or "flat").strip().lower() == "sqrt_adv"


@dataclass
class ExecutionRequest:
    portfolio_id: str
    adapter: AdapterKind = "paper"
    cost_version: str = "v1_ashare_default"
    force: bool = False
    job_id: str | None = None


@dataclass
class ExecutionResult:
    status: str  # committed / blocked / failed / skipped / invalid
    execution_id: str = ""
    portfolio_id: str = ""
    account_id: str = ""
    order_count: int = 0
    fill_count: int = 0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
