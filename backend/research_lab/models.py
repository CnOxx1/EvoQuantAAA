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
class EvidenceRequest:
    start: str
    end: str
    universe_code: str = "TOP100"
    factor_type: str = "qfq"
    factor_codes: list[str] = field(default_factory=list)
    require_dq: bool = True
    compute_first: bool = False
    year_split: bool = True  # 兼容：True≈split_mode=year
    split_mode: str = "year"  # year | walk_forward | none
    wf_train_days: int = 60
    wf_test_days: int = 20
    wf_step_days: int | None = None
    job_id: str | None = None
    soft_gates: dict[str, Any] | None = None
    hard_oos_gates: dict[str, Any] | None = None


@dataclass
class EvidenceResult:
    status: str
    run_id: str = ""
    universe_code: str = ""
    start: str = ""
    end: str = ""
    message: str = ""
    pack: dict[str, Any] = field(default_factory=dict)


@dataclass
class FreezeRequest:
    evidence_run_id: str
    actor: str = "cli"
    reason: str | None = None
    job_id: str | None = None
    hard_oos_gates: dict[str, Any] | None = None
    force: bool = False


@dataclass
class FreezeResult:
    status: str  # frozen | rejected | failed | skipped
    freeze_id: str = ""
    evidence_run_id: str = ""
    artifact_hash: str = ""
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
