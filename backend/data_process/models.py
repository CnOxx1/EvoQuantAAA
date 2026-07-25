from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ProcessKind = Literal["equity_1d", "index_1d", "fundamental_pit"]

P0_KINDS: tuple[ProcessKind, ...] = ("equity_1d", "index_1d")


@dataclass
class ProcessRequest:
    kind: ProcessKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    index_symbols: list[str] = field(default_factory=list)
    factor_type: str = "qfq"
    preferred_source: str = "akshare"
    job_id: str | None = None


@dataclass
class ProcessResult:
    kind: ProcessKind
    status: str
    process_batch_id: str
    input_rows: int = 0
    output_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_no_factor: int = 0
    message: str = ""
