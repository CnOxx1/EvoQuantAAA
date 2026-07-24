from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IngestKind = Literal["statement", "indicator", "consensus"]

VALID_KINDS: tuple[str, ...] = ("statement", "indicator", "consensus")
P1_KINDS: tuple[str, ...] = ("statement", "indicator")

StatementType = Literal["INCOME", "BALANCE", "CASHFLOW"]
ALL_STATEMENT_TYPES: tuple[str, ...] = ("INCOME", "BALANCE", "CASHFLOW")


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    statement_types: list[str] = field(default_factory=list)
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
