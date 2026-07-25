from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IngestKind = Literal["win_bid", "major_contract"]

VALID_KINDS: tuple[str, ...] = ("win_bid", "major_contract")


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


@dataclass
class FetchBundle:
    kind: IngestKind
    rows: list[dict[str, Any]]
    source: str
