from __future__ import annotations

from pydantic import BaseModel, Field


class PromoteBody(BaseModel):
    to: str = Field(..., description="BACKTESTED|PAPER|LIVE|RETIRED")
    backtest_run: str | None = None
    reason: str | None = None
    skip_gates: bool = False
    gate_version: str | None = None


class KillBody(BaseModel):
    scope: str = "GLOBAL"
    is_on: bool
    reason: str | None = None


class ReviewBody(BaseModel):
    portfolio_id: str | None = None
    drafts: bool = False
    as_of: str | None = None
    force: bool = False


class SignalRunBody(BaseModel):
    as_of: str = Field(..., description="业务日 YYYY-MM-DD")
    strategy_version: str | None = None
    paper: bool = True
    live: bool = False
    require_dq: bool = True


class PortfolioBuildBody(BaseModel):
    as_of: str
    strategy_version: str | None = None
    account_id: str = "paper_default"
    paper: bool = True
    live: bool = False
    nav: float = 1_000_000.0
    use_ledger_nav: bool = True
    force: bool = False
    signal_batch_id: str | None = None


class ExecutionRunBody(BaseModel):
    portfolio_id: str | None = None
    approved: bool = False
    as_of: str | None = None
    account_id: str | None = None
    adapter: str = "paper"
    force: bool = False


class ResumePendingBody(BaseModel):
    as_of: str
    account_id: str = "paper_default"
    adapter: str = "paper"
    strategy_version: str | None = None


class LedgerPostBody(BaseModel):
    execution_id: str
    account_id: str | None = None
    force: bool = False
