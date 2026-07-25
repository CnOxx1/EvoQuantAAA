from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UniverseCode = Literal[
    "ALL_LISTED",
    "HS300",
    "HS300_EX_ST",
    "TOP100",
    "SECTOR_LEADERS",
]

# CLI / 校验用全量可选
UNIVERSE_CHOICES: tuple[str, ...] = (
    "ALL_LISTED",
    "HS300",
    "HS300_EX_ST",
    "TOP100",
    "SECTOR_LEADERS",
)

# 默认本地沉淀：市值/股本 Top100 + 各行业龙头（不全市场灌数）
P0_UNIVERSES: tuple[UniverseCode, ...] = ("TOP100", "SECTOR_LEADERS")

# 推荐 ingest 默认 Universe（非 ALL_LISTED）
DEFAULT_INGEST_UNIVERSE: UniverseCode = "TOP100"

SECTOR_LEADER_TOP_K = 1
TOP100_SIZE = 100


@dataclass
class UniverseBuildRequest:
    universe_code: UniverseCode
    as_of_date: str
    industry_standard: str = "SW2021"
    preferred_source: str = "akshare"
    index_symbol: str = "000300"
    job_id: str | None = None
    allow_non_open_day: bool = True
    top_n: int = TOP100_SIZE
    sector_top_k: int = SECTOR_LEADER_TOP_K


@dataclass
class UniverseBuildResult:
    status: str
    universe_snapshot_id: str
    universe_code: str
    as_of_date: str
    member_count: int = 0
    message: str = ""
