from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DqScope = Literal["CORE", "ALPHA"]


@dataclass
class DqRequest:
    scope: DqScope = "CORE"
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    index_symbols: list[str] = field(default_factory=list)
    factor_type: str = "qfq"
    job_id: str | None = None


@dataclass
class RuleOutcome:
    rule_code: str
    severity: Literal["error", "warn"]
    status: Literal["pass", "fail"]
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class DqRunResult:
    dq_run_id: str
    scope: str
    status: str  # passed / failed
    start: str | None
    end: str | None
    factor_type: str
    error_fails: int = 0
    warn_fails: int = 0
    rule_count: int = 0
    message: str = ""
