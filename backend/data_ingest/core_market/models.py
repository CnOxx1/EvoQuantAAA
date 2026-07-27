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
    "market_rank",
    "abnormal_move",
    "board_1d",
    "equity_15m",
    "equity_60m",
]

VALID_KINDS: tuple[str, ...] = (
    "equity_1d",
    "adj_factor",
    "suspend",
    "limit",
    "index_1d",
    "corp_action",
    "market_rank",
    "abnormal_move",
    "board_1d",
    "equity_15m",
    "equity_60m",
)

MIN_BAR_KINDS: tuple[str, ...] = ("equity_15m", "equity_60m")
KIND_TO_FREQ: dict[str, str] = {"equity_15m": "15m", "equity_60m": "60m"}

P0_KINDS: tuple[str, ...] = (
    "equity_1d",
    "adj_factor",
    "suspend",
    "limit",
    "index_1d",
)

# 排名类型：涨跌幅涨/跌榜、成交量、成交额、换手、人气
RANK_TYPES: tuple[str, ...] = (
    "PCT_CHG_UP",
    "PCT_CHG_DOWN",
    "VOLUME",
    "AMOUNT",
    "TURNOVER",
    "HOT",
)

DEFAULT_RANK_TOP_N = 100

BOARD_TYPES: tuple[str, ...] = ("INDUSTRY", "CONCEPT")

# 东财盘口异动类型（stock_changes_em 的 symbol 参数）
ABNORMAL_CHANGE_TYPES: tuple[str, ...] = (
    "火箭发射",
    "快速反弹",
    "大笔买入",
    "封涨停板",
    "打开跌停板",
    "有大买盘",
    "竞价上涨",
    "高开5日线",
    "向上缺口",
    "60日新高",
    "60日大幅上涨",
    "加速下跌",
    "高台跳水",
    "大笔卖出",
    "封跌停板",
    "打开涨停板",
    "有大卖盘",
    "竞价下跌",
    "低开5日线",
    "向下缺口",
    "60日新低",
    "60日大幅下跌",
)


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    index_symbols: list[str] = field(default_factory=list)
    job_id: str | None = None
    top_n: int = DEFAULT_RANK_TOP_N
    rank_types: list[str] = field(default_factory=list)
    prefer_spot: bool = False
    change_types: list[str] = field(default_factory=list)
    board_types: list[str] = field(default_factory=list)
    board_names: list[str] = field(default_factory=list)


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0


@dataclass
class FetchBundle:
    kind: IngestKind
    rows: list[dict[str, Any]]
    source: str
