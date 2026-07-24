from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


IngestKind = Literal[
    "ann_incremental",
    "ann_watchlist",
    "ann_backfill",
    "ann_by_category",
]

VALID_KINDS: tuple[str, ...] = (
    "ann_incremental",
    "ann_watchlist",
    "ann_backfill",
    "ann_by_category",
)


@dataclass(frozen=True)
class AnnouncementRecord:
    source_ann_id: str
    title: str
    publish_time: str
    category_raw: str
    channel: str
    source: str
    symbol: str | None = None
    category_norm: str | None = None
    url: str | None = None
    content_uri: str | None = None
    content_hash: str | None = None


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] | None = None
    categories: list[str] | None = None
    page_size: int = 30
    max_pages: int = 5
    job_id: str | None = None
