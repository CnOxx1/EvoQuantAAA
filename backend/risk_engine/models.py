from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RiskLimits:
    version: str = "v1_default"
    max_single_weight: float = 0.15
    max_names: int = 50
    max_gross_exposure: float = 1.01
    min_names: int = 1
    lot_size: int = 100


@dataclass
class RiskReviewRequest:
    portfolio_id: str
    limits_version: str = "v1_default"
    actor: str = "cli"
    job_id: str | None = None
    # True：即使已有 decision 也重审并覆盖 portfolio 状态
    force: bool = False


@dataclass
class RiskReviewResult:
    status: str  # approved / rejected / skipped / failed / invalid
    decision_id: str = ""
    portfolio_id: str = ""
    account_id: str = ""
    breach_count: int = 0
    breaches: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
