from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IngestKind = Literal["hot_relate", "holder_team", "board_co"]

VALID_KINDS: tuple[str, ...] = ("hot_relate", "holder_team", "board_co")

# 股东协同接口允许的 holder type
HOLDER_TYPES: tuple[str, ...] = (
    "社保",
    "基金",
    "QFII",
    "券商",
    "信托",
    "个人",
    "全部",
)

BoardType = Literal["CONCEPT", "INDUSTRY"]


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None  # as_of / 区间起点（board 可选）
    end: str | None = None  # as_of 默认今日
    symbols: list[str] = field(default_factory=list)
    holder_type: str = "社保"
    board_type: BoardType = "CONCEPT"
    board_names: list[str] = field(default_factory=list)
    max_pair_stocks: int = 12  # holder_team 单条明细最多展开多少只股
    job_id: str | None = None


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0


@dataclass
class FetchBundle:
    kind: IngestKind
    rows: list[dict[str, Any]]
    source: str
