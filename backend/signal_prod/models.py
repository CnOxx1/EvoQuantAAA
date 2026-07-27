from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalRunRequest:
    strategy_version: str
    start: str
    end: str
    as_of: str | None = None
    require_dq: bool = True
    job_id: str | None = None


@dataclass
class SignalRunResult:
    status: str  # committed / failed / skipped / invalid
    signal_batch_id: str = ""
    strategy_version: str = ""
    strategy_code: str = ""
    start: str = ""
    end: str = ""
    row_count: int = 0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
