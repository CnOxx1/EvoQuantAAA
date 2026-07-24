from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

IngestKind = Literal["news_incremental", "news_watchlist", "news_backfill"]

VALID_KINDS: tuple[str, ...] = (
    "news_incremental",
    "news_watchlist",
    "news_backfill",
)


@dataclass(frozen=True)
class NewsRecord:
    source_news_id: str
    title: str
    publish_time: str
    channel: str
    source: str
    symbol: str | None = None
    summary: str | None = None
    url: str | None = None
    media_source: str | None = None


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    job_id: str | None = None


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
