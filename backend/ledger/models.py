from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PostRequest:
    execution_id: str
    account_id: str | None = None  # 默认取 execution_run.account_id
    job_id: str | None = None
    force: bool = False


@dataclass
class PostResult:
    status: str  # committed / skipped / failed / invalid / blocked
    posting_id: str = ""
    execution_id: str = ""
    account_id: str = ""
    entry_count: int = 0
    cash_after: float = 0.0
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
