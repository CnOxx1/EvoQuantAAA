from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FactorCode = Literal[
    "MOM_20",
    "VAL_PE_PCT",
    "FLOW_NET_5",
    "TECH_RSI_14",
    "TECH_MACD_HIST",
    "TECH_MA20_BIAS",
]
FACTOR_CODES: tuple[FactorCode, ...] = (
    "MOM_20",
    "VAL_PE_PCT",
    "FLOW_NET_5",
    "TECH_RSI_14",
    "TECH_MACD_HIST",
    "TECH_MA20_BIAS",
)


@dataclass
class ResearchRequest:
    factor_code: FactorCode
    start: str
    end: str
    universe_code: str = "TOP100"
    factor_type: str = "qfq"
    require_dq: bool = True
    job_id: str | None = None


@dataclass
class ResearchResult:
    status: str
    run_id: str
    factor_code: str
    universe_code: str
    start: str
    end: str
    row_count: int = 0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
