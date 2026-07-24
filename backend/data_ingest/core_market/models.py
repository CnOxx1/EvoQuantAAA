from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IngestKind = Literal[
    "equity_1d",
    "adj_factor",
    "suspend",
    "limit",
    "index_1d",
    "corp_action",
]

VALID_KINDS: tuple[str, ...] = (
    "equity_1d",
    "adj_factor",
    "suspend",
    "limit",
    "index_1d",
    "corp_action",
)

P0_KINDS: tuple[str, ...] = (
    "equity_1d",
    "adj_factor",
    "suspend",
    "limit",
    "index_1d",
)


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    index_symbols: list[str] = field(default_factory=list)
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
