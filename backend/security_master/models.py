from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

UniverseCode = Literal["ALL_LISTED", "HS300", "HS300_EX_ST"]

P0_UNIVERSES: tuple[UniverseCode, ...] = ("ALL_LISTED", "HS300", "HS300_EX_ST")


@dataclass
class UniverseBuildRequest:
    universe_code: UniverseCode
    as_of_date: str
    industry_standard: str = "SW2021"
    preferred_source: str = "akshare"
    index_symbol: str = "000300"
    job_id: str | None = None
    allow_non_open_day: bool = True


@dataclass
class UniverseBuildResult:
    status: str
    universe_snapshot_id: str
    universe_code: str
    as_of_date: str
    member_count: int = 0
    message: str = ""
