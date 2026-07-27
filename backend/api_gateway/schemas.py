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
