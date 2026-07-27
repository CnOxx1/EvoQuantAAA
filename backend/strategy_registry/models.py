from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StrategyKind = Literal["FACTOR_TOP_N"]
STRATEGY_KINDS: tuple[StrategyKind, ...] = ("FACTOR_TOP_N",)

StrategyStatus = Literal["DRAFT", "BACKTESTED", "PAPER", "LIVE", "RETIRED"]
STRATEGY_STATUSES: tuple[StrategyStatus, ...] = (
    "DRAFT",
    "BACKTESTED",
    "PAPER",
    "LIVE",
    "RETIRED",
)

# 允许的状态迁移（审计落库）
ALLOWED_TRANSITIONS: frozenset[tuple[StrategyStatus, StrategyStatus]] = frozenset(
    {
        ("DRAFT", "BACKTESTED"),
        ("DRAFT", "RETIRED"),
        ("BACKTESTED", "PAPER"),
        ("BACKTESTED", "RETIRED"),
        ("PAPER", "LIVE"),
        ("PAPER", "RETIRED"),
        ("LIVE", "PAPER"),
        ("LIVE", "RETIRED"),
    }
)

# signal_prod 可运行的状态
SIGNAL_RUNNABLE_STATUSES: frozenset[StrategyStatus] = frozenset({"PAPER", "LIVE"})


@dataclass
class RegisterRequest:
    strategy_code: str
    strategy_kind: StrategyKind
    params: dict[str, Any]
    research_run_id: str | None = None
    backtest_run_id: str | None = None
    note: str | None = None
    actor: str = "cli"


@dataclass
class PromoteRequest:
    strategy_version: str
    to_status: StrategyStatus
    backtest_run_id: str | None = None
    reason: str | None = None
    actor: str = "cli"
    # 晋升 LIVE 时若已有同 code LIVE：retire_previous=True 则自动停用旧版
    retire_previous_live: bool = True


@dataclass
class StrategyRecord:
    strategy_version: str
    strategy_code: str
    strategy_kind: str
    status: str
    params: dict[str, Any]
    research_run_id: str | None = None
    backtest_run_id: str | None = None
    artifact_hash: str | None = None
    note: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RegistryResult:
    status: str  # ok / failed / invalid
    strategy_version: str = ""
    strategy_code: str = ""
    from_status: str = ""
    to_status: str = ""
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
