from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# 内置种子码（迁移 039 同步写入 research_factor_def）
FactorCode = Literal[
    "MOM_20",
    "VAL_PE_PCT",
    "FLOW_NET_5",
    "TECH_RSI_14",
    "TECH_MACD_HIST",
    "TECH_MA20_BIAS",
]
FACTOR_CODES: tuple[str, ...] = (
    "MOM_20",
    "VAL_PE_PCT",
    "FLOW_NET_5",
    "TECH_RSI_14",
    "TECH_MACD_HIST",
    "TECH_MA20_BIAS",
)

FACTOR_TEMPLATES: tuple[str, ...] = (
    "MOM",
    "VAL_PE_PCT",
    "FLOW_NET",
    "TECH_PASS",
    "TECH_RSI",
    "TECH_MACD_HIST",
    "TECH_MA_BIAS",
)

BUILTIN_SPECS: dict[str, dict[str, Any]] = {
    "MOM_20": {"template": "MOM", "params": {"lookback": 20}},
    "VAL_PE_PCT": {"template": "VAL_PE_PCT", "params": {}},
    "FLOW_NET_5": {"template": "FLOW_NET", "params": {"lookback": 5}},
    "TECH_RSI_14": {"template": "TECH_RSI", "params": {"period": 14}},
    "TECH_MACD_HIST": {"template": "TECH_MACD_HIST", "params": {}},
    "TECH_MA20_BIAS": {"template": "TECH_MA_BIAS", "params": {"period": 20}},
}


@dataclass
class ResearchRequest:
    factor_code: str
    start: str
    end: str
    universe_code: str = "TOP100"
    factor_type: str = "qfq"
    require_dq: bool = True
    job_id: str | None = None


@dataclass
class ResearchResult:
    status: str
    run_id: str = ""
    factor_code: str = ""
    universe_code: str = ""
    start: str = ""
    end: str = ""
    row_count: int = 0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorDefUpsert:
    factor_code: str
    template: str
    params: dict[str, Any] = field(default_factory=dict)
    display_name: str = ""
    description: str | None = None
    status: str = "ACTIVE"
    actor: str = "api"


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
