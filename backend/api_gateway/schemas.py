from __future__ import annotations

from pydantic import BaseModel, Field


class PromoteBody(BaseModel):
    to: str = Field(..., description="BACKTESTED|PAPER|LIVE|RETIRED")
    backtest_run: str | None = None
    reason: str | None = None
    skip_gates: bool = False
    gate_version: str | None = None


class RegisterBody(BaseModel):
    strategy_code: str = Field(..., description="如 FTN_MOM20")
    strategy_kind: str = Field("FACTOR_TOP_N", description="当前仅 FACTOR_TOP_N")
    factor_code: str = Field(..., description="如 MOM_20")
    top_n: int = Field(20, ge=1)
    rebalance_days: int = Field(20, ge=1)
    universe_code: str = "TOP100"
    factor_type: str = Field("qfq", description="qfq|hfq")
    research_run_id: str | None = None
    backtest_run_id: str | None = None
    note: str | None = None


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


class ScheduleOnceBody(BaseModel):
    as_of: str = Field(..., description="业务日 YYYY-MM-DD")
    universe: str = "TOP100"
    factor_type: str = "qfq"
    force: bool = False


class BacktestRunBody(BaseModel):
    strategy: str = Field("FACTOR_TOP_N", description="EW_HOLD|EW_REBALANCE|FACTOR_TOP_N")
    start: str
    end: str
    universe: str = "TOP100"
    factor_type: str = "qfq"
    factor: str | None = Field(None, description="FACTOR_TOP_N 必填，如 MOM_20")
    top_n: int = Field(20, ge=1)
    rebalance_days: int = Field(20, ge=0)
    benchmark: str = "000300"
    cash: float = 1_000_000.0
    require_dq: bool = True
    cost_version: str = "v1_ashare_default"


class FactorDefBody(BaseModel):
    factor_code: str = Field(..., description="如 MOM_30")
    template: str = Field(
        ...,
        description="MOM|VAL_PE_PCT|FLOW_NET|TECH_PASS|TECH_RSI|TECH_MACD_HIST|TECH_MA_BIAS",
    )
    params: dict = Field(default_factory=dict)
    display_name: str = ""
    description: str | None = None
    status: str = "ACTIVE"


class FactorDefPatchBody(BaseModel):
    display_name: str | None = None
    params: dict | None = None
    description: str | None = None
    status: str | None = None


class ResearchRunBody(BaseModel):
    factor_code: str
    start: str
    end: str
    universe_code: str = "TOP100"
    factor_type: str = "qfq"
    require_dq: bool = True
