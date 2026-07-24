from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IngestKind = Literal[
    "calendar",
    "listing",
    "industry",
    "share_capital",
    "index_member",
    "special_treat",
]

VALID_KINDS: tuple[str, ...] = (
    "calendar",
    "listing",
    "industry",
    "share_capital",
    "index_member",
    "special_treat",
)

P0_KINDS: tuple[str, ...] = ("calendar", "listing", "industry", "share_capital")


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    exchange: str = "SSE"
    industry_standard: str = "SW2021"
    index_symbols: list[str] = field(default_factory=list)
    job_id: str | None = None


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0


@dataclass
class FetchBundle:
    """按 kind 承载一类记录（dict 行，由 repository 解释）。"""

    kind: IngestKind
    rows: list[dict[str, Any]]
    source: str
