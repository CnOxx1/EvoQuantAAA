from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioBuildRequest:
    strategy_version: str
    as_of: str
    nav: float = 1_000_000.0
    account_id: str = "paper_default"
    cost_version: str = "v1_ashare_default"
    # 若指定则用该批次；否则取 as_of 及之前最近调仓日信号
    signal_batch_id: str | None = None
    require_runnable: bool = True
    # True：同日已有 draft/approved/executed 时仍新建（先需人工处理唯一约束）
    force: bool = False
    # None=用请求 nav；True=用账本权益估算覆盖 nav
    use_ledger_nav: bool = False
    # 同账户资本配额（build_all_runnable 写入；单次 build 可选）
    capital_weight: float | None = None
    # True：仅当 signal_trade_date == as_of 才新建（非调仓日 hold）
    require_signal_as_of: bool = False
    job_id: str | None = None


@dataclass
class PortfolioBuildResult:
    status: str  # committed / failed / skipped / invalid
    portfolio_id: str = ""
    strategy_version: str = ""
    strategy_code: str = ""
    as_of: str = ""
    row_count: int = 0
    invested_value: float = 0.0
    cash_residual: float = 0.0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
